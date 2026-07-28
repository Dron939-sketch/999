//! Timeline compiler — transforms scene statements into a flat list of
//! keyframe tracks that can be evaluated at any time `t`.

use std::collections::HashMap;

use crate::ast::*;
use crate::errors::AnimError;
use crate::scene::{resolve_position, EntityState, ResolvedScene};

/// A compiled timeline for one scene.
#[derive(Debug)]
pub struct Timeline {
    pub duration: f64,
    pub tracks: Vec<Track>,
    pub pose_events: Vec<PoseEvent>,
    /// Speech blocks (start,end) in scene time — one per voiced line
    /// (a `speaks` action or an uninterrupted run of `lips` actions).
    pub speech_blocks: Vec<(f64, f64)>,
    pub camera_track: CameraTrack,
    pub transitions: Vec<TransitionEvent>,
}

/// A track of keyframes for a single entity property.
#[derive(Debug, Clone)]
pub struct Track {
    pub entity: String,
    pub property: Property,
    pub keyframes: Vec<Keyframe>,
}

/// The animatable properties.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Property {
    X,
    Y,
    ScaleX,
    ScaleY,
    Rotation,
    Opacity,
}

/// A single keyframe: at time `t`, the value is `value`, interpolated with `easing`.
#[derive(Debug, Clone)]
pub struct Keyframe {
    pub time: f64,
    pub value: f64,
    pub easing: Easing,
}

/// Pose changes are discrete (not interpolated).
#[derive(Debug, Clone)]
pub struct PoseEvent {
    pub time: f64,
    pub entity: String,
    pub pose: String,
    /// Overlay events (auto-speech mouth flaps) merge onto the last held
    /// full pose instead of replacing it — the body keeps its gesture.
    pub overlay: bool,
}

/// Camera keyframes.
#[derive(Debug)]
pub struct CameraTrack {
    pub keyframes: Vec<CameraKeyframe>,
}

#[derive(Debug, Clone)]
pub struct CameraKeyframe {
    pub time: f64,
    /// Camera center in normalized coords.
    pub x: f64,
    pub y: f64,
    /// Zoom level (1.0 = full scene visible).
    pub zoom: f64,
    /// Крен кадра в градусах (dutch-угол); 0 = ровно.
    pub roll: f64,
    /// Вертикальный ракурс (наклон объектива) в градусах. >0 — камера сверху
    /// (смотрит вниз), <0 — снизу (вверх), 0 — на уровне глаз. Двигатель
    /// превращает это в форшортенинг по высоте фигуры (ближняя часть крупнее).
    pub pitch: f64,
    pub easing: Easing,
    /// Optional shake intensity (0 = no shake).
    pub shake: f64,
}

/// Transition events (fade-black, dissolve, etc.).
#[derive(Debug, Clone)]
pub struct TransitionEvent {
    pub time: f64,
    pub kind: TransitionKind,
    pub duration: f64,
}

#[derive(Debug, Clone)]
pub enum TransitionKind {
    FadeBlack,
    FadeWhite,
    Cut,
    Static,
    Invert,
    Dissolve,
    Wipe(Direction),
}

/// Compile a resolved scene into a timeline.
pub fn compile(scene: &ResolvedScene) -> Result<Timeline, AnimError> {
    compile_with_kartas(scene, &HashMap::new())
}

/// То же, но с картами фигур персонажей (см. `skeleton::Karta`): по ним
/// считается кадрирование планов. Без карт поведение прежнее.
pub fn compile_with_kartas(
    scene: &ResolvedScene,
    kartas: &HashMap<String, crate::skeleton::Karta>,
) -> Result<Timeline, AnimError> {
    compile_full(scene, kartas, None)
}

/// То же, но с полом локации: нужен, чтобы КАДРИРОВАНИЕ знало про `on floor`.
pub fn compile_full(
    scene: &ResolvedScene,
    kartas: &HashMap<String, crate::skeleton::Karta>,
    floor: Option<crate::assets::Floor>,
) -> Result<Timeline, AnimError> {
    let mut compiler = TimelineCompiler {
        time: 0.0,
        tracks: HashMap::new(),
        pose_events: Vec::new(),
        speech_blocks: Vec::new(),
        lips_open: None,
        camera_keyframes: vec![CameraKeyframe {
            time: 0.0,
            x: 0.5,
            y: 0.5,
            zoom: 1.0,
            easing: Easing::Linear,
            shake: 0.0,
            roll: 0.0,
            pitch: 0.0,
        }],
        transitions: Vec::new(),
        entities: scene.entities.clone(),
        kartas: kartas.clone(),
        floor,
    };

    compiler.compile_statements(&scene.statements)?;

    // Convert the tracks HashMap into a Vec<Track>.
    let tracks = compiler
        .tracks
        .into_iter()
        .flat_map(|(entity, props)| {
            props.into_iter().map(move |(property, keyframes)| Track {
                entity: entity.clone(),
                property,
                keyframes,
            })
        })
        .collect();

    // Use the longer of the declared duration or the actual action timeline.
    let actual_duration = compiler.time;
    let duration = scene.duration.max(actual_duration);

    Ok(Timeline {
        duration,
        tracks,
        pose_events: compiler.pose_events,
        speech_blocks: compiler.speech_blocks,
        camera_track: CameraTrack {
            keyframes: compiler.camera_keyframes,
        },
        transitions: compiler.transitions,
    })
}

struct TimelineCompiler {
    time: f64,
    /// entity -> property -> keyframes
    tracks: HashMap<String, HashMap<Property, Vec<Keyframe>>>,
    pose_events: Vec<PoseEvent>,
    speech_blocks: Vec<(f64, f64)>,
    lips_open: Option<usize>,
    camera_keyframes: Vec<CameraKeyframe>,
    transitions: Vec<TransitionEvent>,
    entities: HashMap<String, EntityState>,
    /// Карты фигур: имя сущности -> замеренная карта персонажа.
    kartas: HashMap<String, crate::skeleton::Karta>,
    /// Пол текущей локации — для сущностей, объявленных `on floor`.
    floor: Option<crate::assets::Floor>,
}

impl TimelineCompiler {
    fn compile_statements(&mut self, stmts: &[SceneStatement]) -> Result<(), AnimError> {
        for stmt in stmts {
            self.compile_statement(stmt)?;
        }
        Ok(())
    }

    fn compile_statement(&mut self, stmt: &SceneStatement) -> Result<(), AnimError> {
        // Границы речевых блоков: непрерывный ряд `lips` = одна реплика; любое
        // другое утверждение (поза, камера, wait) закрывает текущий блок.
        if !matches!(stmt, SceneStatement::Action(ActionStmt::Lips { .. })) {
            self.lips_open = None;
        }
        match stmt {
            SceneStatement::Place(_) => {
                // Already handled during scene resolution.
                Ok(())
            }
            SceneStatement::Wait(dur) => {
                self.time += dur.as_secs();
                Ok(())
            }
            SceneStatement::Action(action) => self.compile_action(action),
            SceneStatement::Together(stmts) => {
                // All statements in a together block start at the same time.
                let start_time = self.time;
                let mut max_end = self.time;
                for s in stmts {
                    self.time = start_time;
                    self.compile_statement(s)?;
                    max_end = max_end.max(self.time);
                }
                self.time = max_end;
                Ok(())
            }
            SceneStatement::Do(stmts) => {
                // Sequential — just compile each in order.
                self.compile_statements(stmts)
            }
            SceneStatement::Camera(cam) => self.compile_camera(cam),
            SceneStatement::Transition(tr) => self.compile_transition(tr),
            SceneStatement::Let(_) => {
                // Let bindings are handled during asset loading.
                Ok(())
            }
        }
    }

    fn compile_action(&mut self, action: &ActionStmt) -> Result<(), AnimError> {
        match action {
            ActionStmt::MoveTo {
                entity,
                target,
                duration,
                easing,
            } => {
                let (tx, ty) = resolve_position(target, &self.entities)?;
                let easing = easing.unwrap_or(Easing::EaseInOut);
                let dur = duration.as_secs();

                self.ensure_current_keyframe(entity, Property::X);
                self.ensure_current_keyframe(entity, Property::Y);

                self.add_keyframe(entity, Property::X, self.time + dur, tx, easing);
                self.add_keyframe(entity, Property::Y, self.time + dur, ty, easing);

                // Update entity state.
                if let Some(e) = self.entities.get_mut(entity) {
                    e.x = tx;
                    e.y = ty;
                }

                self.time += dur;
            }
            ActionStmt::Pose { entity, pose } => {
                self.pose_events.push(PoseEvent {
                    time: self.time,
                    entity: entity.clone(),
                    pose: pose.clone(),
                    overlay: false,
                });
                if let Some(e) = self.entities.get_mut(entity) {
                    e.pose = pose.clone();
                }
            }
            ActionStmt::Overlay { entity, pose } => {
                // Слой: событие помечается overlay, и рендер сливает кости этой
                // позы поверх последней ПОЛНОЙ позы. Состояние сущности при
                // этом не меняется — база остаётся прежней, иначе следующий
                // слой лёг бы уже на слой, и вернуться к базовой позе было бы
                // нечем.
                self.pose_events.push(PoseEvent {
                    time: self.time,
                    entity: entity.clone(),
                    pose: pose.clone(),
                    overlay: true,
                });
            }
            ActionStmt::Speak { entity, duration } => {
                // Auto-speech: cycle phoneme mouth poses for the duration and
                // advance time (a wait that talks). The pattern is deterministic
                // but irregular so the flapping doesn't read as a metronome.
                // Flaps are overlays: they merge onto the held body pose.
                let dur = duration.as_secs();
                let end = self.time + dur;
                self.speech_blocks.push((self.time, end));
                // Закрытый рот — `visA` (ТОЛЬКО кость рта), а не `idle`.
                // `idle` задаёт ещё руки, кисть и голову: каждый четвёртый флэп
                // сбрасывал жест говорящего в покой на один рисунок. На речи в
                // позе `lunge` это читалось дёрганьем рук примерно раз в
                // полсекунды — тем более заметным, что мы держим 12 рисунков в
                // секунду.
                const FLAPS: [&str; 6] = ["talk", "gab", "talk", "visA", "gab", "talk"];
                let mut t = self.time;
                let mut i: usize = 0;
                while t < end - 0.05 {
                    self.pose_events.push(PoseEvent {
                        time: t,
                        entity: entity.clone(),
                        pose: FLAPS[i % FLAPS.len()].to_string(),
                        overlay: true,
                    });
                    // 0.14–0.24s per flap, varied deterministically.
                    t += 0.14 + 0.05 * ((i * 7 + 3) % 3) as f64;
                    i += 1;
                }
                // Закрыть рот в конце реплики — тоже мимо тела: `visA`.
                self.pose_events.push(PoseEvent {
                    time: end,
                    entity: entity.clone(),
                    pose: "visA".to_string(),
                    overlay: true,
                });
                self.time = end;
            }
            ActionStmt::Lips {
                entity,
                pose,
                duration,
            } => {
                // One overlay mouth cel held for the duration. Overlay merges
                // onto the held body pose, so a lying/gesturing character keeps
                // its posture while the mouth follows the real audio envelope.
                self.pose_events.push(PoseEvent {
                    time: self.time,
                    entity: entity.clone(),
                    pose: pose.clone(),
                    overlay: true,
                });
                let start = self.time;
                self.time += duration.as_secs();
                match self.lips_open {
                    Some(i) => self.speech_blocks[i].1 = self.time,
                    None => {
                        self.speech_blocks.push((start, self.time));
                        self.lips_open = Some(self.speech_blocks.len() - 1);
                    }
                }
            }
            ActionStmt::Show {
                entity,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.3);
                let easing = easing.unwrap_or(Easing::EaseIn);

                self.ensure_current_keyframe(entity, Property::Opacity);
                self.add_keyframe(entity, Property::Opacity, self.time + dur, 1.0, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.opacity = 1.0;
                    e.visible = true;
                }

                self.time += dur;
            }
            ActionStmt::Hide {
                entity,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.3);
                let easing = easing.unwrap_or(Easing::EaseOut);

                self.ensure_current_keyframe(entity, Property::Opacity);
                self.add_keyframe(entity, Property::Opacity, self.time + dur, 0.0, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.opacity = 0.0;
                }

                self.time += dur;
            }
            ActionStmt::Enter {
                entity,
                from,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(1.0);
                let easing = easing.unwrap_or(Easing::EaseOut);

                // Auto-register entity if not already placed.
                if !self.entities.contains_key(entity) {
                    self.entities.insert(
                        entity.clone(),
                        crate::scene::EntityState::new_character(entity),
                    );
                }

                // Start off-screen, move to current position.
                let target_x = self.entities.get(entity).map(|e| e.x).unwrap_or(0.5);
                let target_y = self.entities.get(entity).map(|e| e.y).unwrap_or(0.5);

                let (start_x, start_y) = match from {
                    Direction::Left => (-0.2, target_y),
                    Direction::Right => (1.2, target_y),
                    Direction::Up => (target_x, -0.2),
                    Direction::Down => (target_x, 1.2),
                    Direction::Front | Direction::Back => (target_x, 1.2),
                };

                // Set start position.
                self.set_keyframe(entity, Property::X, self.time, start_x, Easing::Linear);
                self.set_keyframe(entity, Property::Y, self.time, start_y, Easing::Linear);
                self.set_keyframe(entity, Property::Opacity, self.time, 0.0, Easing::Linear);

                // Animate to target.
                self.add_keyframe(entity, Property::X, self.time + dur, target_x, easing);
                self.add_keyframe(entity, Property::Y, self.time + dur, target_y, easing);
                self.add_keyframe(entity, Property::Opacity, self.time + dur, 1.0, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.x = target_x;
                    e.y = target_y;
                    e.opacity = 1.0;
                    e.visible = true;
                }

                self.time += dur;
            }
            ActionStmt::Exit {
                entity,
                to,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(1.0);
                let easing = easing.unwrap_or(Easing::EaseIn);

                let current_x = self.entities.get(entity).map(|e| e.x).unwrap_or(0.5);
                let current_y = self.entities.get(entity).map(|e| e.y).unwrap_or(0.5);

                let (end_x, end_y) = match to {
                    Direction::Left => (-0.2, current_y),
                    Direction::Right => (1.2, current_y),
                    Direction::Up => (current_x, -0.2),
                    Direction::Down => (current_x, 1.2),
                    Direction::Front | Direction::Back => (current_x, 1.2),
                };

                self.ensure_current_keyframe(entity, Property::X);
                self.ensure_current_keyframe(entity, Property::Y);
                self.ensure_current_keyframe(entity, Property::Opacity);

                self.add_keyframe(entity, Property::X, self.time + dur, end_x, easing);
                self.add_keyframe(entity, Property::Y, self.time + dur, end_y, easing);
                self.add_keyframe(entity, Property::Opacity, self.time + dur, 0.0, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.x = end_x;
                    e.y = end_y;
                    e.opacity = 0.0;
                }

                self.time += dur;
            }
            ActionStmt::Scale {
                entity,
                factor,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.5);
                let easing = easing.unwrap_or(Easing::EaseInOut);

                self.ensure_current_keyframe(entity, Property::ScaleX);
                self.ensure_current_keyframe(entity, Property::ScaleY);

                self.add_keyframe(entity, Property::ScaleX, self.time + dur, *factor, easing);
                self.add_keyframe(entity, Property::ScaleY, self.time + dur, *factor, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.scale_x = *factor;
                    e.scale_y = *factor;
                }

                self.time += dur;
            }
            ActionStmt::Rotate {
                entity,
                angle,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.5);
                let easing = easing.unwrap_or(Easing::EaseInOut);

                self.ensure_current_keyframe(entity, Property::Rotation);
                self.add_keyframe(entity, Property::Rotation, self.time + dur, *angle, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.rotation = *angle;
                }

                self.time += dur;
            }
            ActionStmt::FadeTo {
                entity,
                opacity,
                duration,
                easing,
            } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.5);
                let easing = easing.unwrap_or(Easing::EaseInOut);

                self.ensure_current_keyframe(entity, Property::Opacity);
                self.add_keyframe(entity, Property::Opacity, self.time + dur, *opacity, easing);

                if let Some(e) = self.entities.get_mut(entity) {
                    e.opacity = *opacity;
                }

                self.time += dur;
            }
        }
        Ok(())
    }

    /// Кадрирование плана по РАЗМЕРУ фигуры, а не по постоянной.
    ///
    /// Прежние зумы (medium 2.2, close-up 3.4, ecu 6.0) были подобраны на глаз
    /// для персонажа в натуральную величину — `scales 1.0`. Как только фигура
    /// подросла (в тюрьме `scales 1.5`), те же числа стали резать макушку: на
    /// крупном плане голова уезжала за верхний край, потому что зум не знал,
    /// какого роста то, что он приближает.
    ///
    /// Здесь план задан ГЕОМЕТРИЕЙ. Замеры сняты с рендера стенда и выражены в
    /// долях высоты кадра НА ЕДИНИЦУ `scales` (доля от кадра не зависит от
    /// разрешения, потому что рост фигуры сам считается от высоты холста):
    /// якорь сущности сидит на уровне плеч, макушка на 0.19 выше, подбородок
    /// на 0.05 ниже, ступни на 0.45 ниже. Зум делится на масштаб, вертикальный
    /// центр на него умножается — при `scales 1.0` выходят ровно прежние числа,
    /// при любом другом росте план держится тот же.
    fn frame_shot(
        &self,
        shot: ShotType,
        target: Option<&str>,
    ) -> Result<(f64, f64, f64), AnimError> {
        // (смещение центра от якоря, зум) — при scales 1.0, для персонажа без
        // замеренной карты. Числа исторические, подобранные на глаз.
        let (dy, zoom) = match shot {
            ShotType::Wide => return Ok((0.5, 0.5, 1.0)),
            ShotType::Medium => (0.05, 2.2),
            ShotType::CloseUp => (-0.045, 3.4),
            ShotType::ExtremeCloseUp => (-0.06, 6.0),
            ShotType::TwoShot => return Ok((0.5, 0.5, 1.2)),
            ShotType::OverShoulder => return Ok((0.5, 0.45, 1.8)),
        };
        let Some(name) = target else {
            // Без цели роста не знаем — остаются исторические постоянные.
            return Ok((0.5, 0.5 + dy, zoom));
        };
        let e = self
            .entities
            .get(name)
            .ok_or_else(|| AnimError::Timeline(format!("unknown entity: {name}")))?;
        // `on floor`: e.y — это СТУПНИ, а план считается от якоря и от
        // масштаба, уже уменьшенного глубиной. Без этого камера наводилась на
        // точку пола и зумила по негрунтованному размеру: на среднем плане
        // фигура вылезала за кадр.
        let (ey, s) = match (self.floor, self.kartas.get(name)) {
            (Some(f), Some(k)) if e.grounded => {
                let (anchor, d) = f.ground(e.y, e.scale_y, k.feet);
                (anchor, (e.scale_y * d).abs().max(0.05))
            }
            _ => (e.y, e.scale_y.abs().max(0.05)),
        };

        // Есть карта — план считается ГЕОМЕТРИЕЙ этого персонажа: берём
        // верхнюю и нижнюю границы того, что план обязан показать, и подбираем
        // зум так, чтобы они уложились в кадр с полем. Так одна и та же
        // команда `camera close-up` одинаково правильно кадрирует и Фримена, и
        // любого следующего персонажа с другими пропорциями — без единой новой
        // постоянной в движке.
        if let Some(k) = self.kartas.get(name) {
            let head_h = (k.chin - k.crown).abs().max(1e-6);
            let (top, bottom, fill) = match shot {
                // ВОЗДУХ. Фигура целиком и поле вокруг неё.
                //
                // Здесь был поясной план: от макушки до колена при заполнении
                // 0.86. Замер готовых роликов против оригинала
                // (`tools/montage_ref.py`) показал, чего это стоило: у Фримена
                // фигура распирает кадр 26% времени, у нас — от 53% до 82%, во
                // всех шести роликах разом. Причина не в сценариях (они честно
                // чередуют планы), а в геометрии: при росте 0.600 и пролёте
                // 0.491 поясной план выводил фигуру на 1.05 высоты кадра, то
                // есть РЕЗАЛ её рамкой. То же и у `close-up` (2.01), и у `ecu`
                // (3.60). Воздух в кадре давал единственный план — `wide`, а он
                // в сценариях меньшинство.
                //
                // Когда обрезаны все планы, кат между ними не читается: смена
                // крупности видна на 0.22–0.53 катов против 0.60 у оригинала.
                // Ударный сверхкруп обесценивается, потому что он всегда.
                //
                // Теперь лестница различима ПО РАЗМЕРУ ФИГУРЫ, а не только по
                // тому, какую часть тела видно: 0.45 → 0.78 → морда. Поясной
                // план (обрезка по колено) из грамматики ушёл намеренно —
                // именно он и делал сверхкрупом каждый второй кадр.
                ShotType::Medium => (k.crown, k.feet, 0.45),
                // тесно: фигура целиком, но заполняет кадр почти полностью.
                // Воздух ещё есть — обрезает рамкой только `ecu`.
                ShotType::CloseUp => (k.crown, k.feet, 0.78),
                // морда на весь кадр: голова с плечами, рамка режет корпус.
                //
                // Был врез ВНУТРЬ головы (`crown + 0.18h … chin - 0.10h`). Для
                // Фримена, у которого голова — 36% роста, это давало фигуру на
                // 3.60 высоты кадра и работало. Для Фреди, у которого голова
                // 12% роста, тот же врез даёт 10.9 — рендер витрины мимики
                // убивало по памяти (OOM) даже на двух секундах и 16 ГБ.
                //
                // Врез внутрь головы кадрирует по ДОЛЕ ГОЛОВЫ, а стоимость
                // растеризации локации растёт от зума — то есть цена плана
                // зависела от пропорций персонажа и на «головастых» ригах
                // молча выходила за память. Голова с плечами задаёт тот же
                // план от РОСТА: 2.01 у Фримена, 3.45 у Фреди — обе величины
                // рендерились в CI годами (это прежняя геометрия `close-up`).
                ShotType::ExtremeCloseUp => {
                    (k.crown, k.chin + (k.feet - k.chin) * 0.18, 0.96)
                }
                _ => (k.crown, k.feet, 0.90),
            };
            let span = (bottom - top).abs().max(1e-6);
            return Ok((
                e.x,
                ey + (top + bottom) / 2.0 * s,
                fill / (span * s),
            ));
        }

        Ok((e.x, ey + dy * s, zoom / s))
    }

    fn compile_camera(&mut self, cam: &CameraStmt) -> Result<(), AnimError> {
        // Ракурс (pitch) держится ПОПЕРЁК склеек: смена размера плана не сбивает
        // «снизу/сверху». Захватываем текущий наклон на входе в команду.
        let carry_pitch = self.camera_keyframes.last().map(|k| k.pitch).unwrap_or(0.0);
        match cam {
            CameraStmt::ShotType { shot, target } => {
                let (x, y, zoom) = self.frame_shot(*shot, target.as_deref())?;

                // Hard cut: `evaluate_camera` tweens smoothly across the ENTIRE
                // gap since the last keyframe. That gap can be many seconds —
                // e.g. a `speak for Ns` placeholder that prep_lipsync replaces
                // with the real (often longer) voice duration — so without a
                // hold, a punchy "СКЛЕЙКА → крупно" cut renders as a slow dolly
                // zoom instead of an instant Freeman-style cut. Freeze the
                // previous camera state right up to just before this cut, so
                // the actual tween window collapses to ~1 frame.
                if let Some(prev) = self.camera_keyframes.last().cloned() {
                    let hold_time = (self.time - 0.04).max(prev.time);
                    if hold_time > prev.time {
                        self.camera_keyframes.push(CameraKeyframe {
                            time: hold_time,
                            ..prev
                        });
                    }
                }

                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time,
                    x,
                    y,
                    zoom,
                    easing: Easing::EaseInOut,
                    shake: 0.0,
                    roll: 0.0,
                    pitch: carry_pitch,
                });
            }
            CameraStmt::ZoomTo {
                target,
                duration,
                easing,
            } => {
                let e = self
                    .entities
                    .get(target)
                    .ok_or_else(|| AnimError::Timeline(format!("unknown entity: {target}")))?;
                let dur = duration.as_secs();
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time + dur,
                    x: e.x,
                    y: e.y - 0.1,
                    zoom: 2.5,
                    easing: easing.unwrap_or(Easing::EaseInOut),
                    shake: 0.0,
                    roll: 0.0,
                    pitch: carry_pitch,
                });
                self.time += dur;
            }
            CameraStmt::PanTo {
                target,
                duration,
                easing,
            } => {
                let (x, y) = match target {
                    PanTarget::Entity(name) => {
                        let e = self.entities.get(name).ok_or_else(|| {
                            AnimError::Timeline(format!("unknown entity: {name}"))
                        })?;
                        (e.x, e.y)
                    }
                    PanTarget::Position(pos) => resolve_position(pos, &self.entities)?,
                };
                let dur = duration.as_secs();
                // Keep same zoom level as last camera keyframe.
                let last_zoom = self.camera_keyframes.last().map(|k| k.zoom).unwrap_or(1.0);
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time + dur,
                    x,
                    y,
                    zoom: last_zoom,
                    easing: easing.unwrap_or(Easing::EaseInOut),
                    shake: 0.0,
                    roll: 0.0,
                    pitch: carry_pitch,
                });
                self.time += dur;
            }
            CameraStmt::Shake {
                duration,
                intensity,
            } => {
                let dur = duration.as_secs();
                let last = self
                    .camera_keyframes
                    .last()
                    .cloned()
                    .unwrap_or(CameraKeyframe {
                        time: 0.0,
                        x: 0.5,
                        y: 0.5,
                        zoom: 1.0,
                        easing: Easing::Linear,
                        shake: 0.0,
                        roll: 0.0,
                        pitch: carry_pitch,
                    });

                // Start shake.
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time,
                    x: last.x,
                    y: last.y,
                    zoom: last.zoom,
                    easing: Easing::Linear,
                    shake: *intensity,
                    roll: last.roll,
                    pitch: last.pitch,
                });

                // End shake.
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time + dur,
                    x: last.x,
                    y: last.y,
                    zoom: last.zoom,
                    easing: Easing::Linear,
                    shake: 0.0,
                    roll: last.roll,
                    pitch: last.pitch,
                });

                self.time += dur;
            }
            CameraStmt::Dutch { angle } => {
                // Мгновенный крен кадра: держится до следующего плана/reset.
                let last = self
                    .camera_keyframes
                    .last()
                    .cloned()
                    .unwrap_or(CameraKeyframe {
                        time: 0.0,
                        x: 0.5,
                        y: 0.5,
                        zoom: 1.0,
                        easing: Easing::Linear,
                        shake: 0.0,
                        roll: 0.0,
                        pitch: carry_pitch,
                    });
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time,
                    x: last.x,
                    y: last.y,
                    zoom: last.zoom,
                    easing: Easing::Linear,
                    shake: last.shake,
                    roll: *angle,
                    pitch: last.pitch,
                });
            }
            CameraStmt::Pitch { angle } => {
                // Мгновенная смена ракурса, держится до следующего pitch/reset.
                let last = self.camera_keyframes.last().cloned().unwrap_or(CameraKeyframe {
                    time: 0.0,
                    x: 0.5,
                    y: 0.5,
                    zoom: 1.0,
                    easing: Easing::Linear,
                    shake: 0.0,
                    roll: 0.0,
                    pitch: 0.0,
                });
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time,
                    x: last.x,
                    y: last.y,
                    zoom: last.zoom,
                    easing: Easing::Linear,
                    shake: last.shake,
                    roll: last.roll,
                    pitch: *angle,
                });
            }
            CameraStmt::Angle { kind, target } => {
                // Пресет ракурса: наклон объектива + вертикальное кадрирование.
                // Низ (снизу вверх) — фигура возвышается: центр ниже, наклон −.
                // Верх (сверху вниз) — фигура придавлена: центр выше, наклон +.
                let (pitch, dy) = match kind {
                    crate::ast::AngleKind::Low => (-26.0, 0.10),
                    crate::ast::AngleKind::High => (26.0, -0.10),
                    crate::ast::AngleKind::Level => (0.0, 0.0),
                };
                let (cx, cy, zoom) = if let Some(name) = target {
                    let e = self.entities.get(name).ok_or_else(|| {
                        AnimError::Timeline(format!("unknown entity: {name}"))
                    })?;
                    (e.x, (e.y + dy).clamp(0.1, 0.9), 1.0)
                } else {
                    (0.5, (0.5 + dy).clamp(0.1, 0.9), 1.0)
                };
                if let Some(prev) = self.camera_keyframes.last().cloned() {
                    let hold_time = (self.time - 0.04).max(prev.time);
                    if hold_time > prev.time {
                        self.camera_keyframes.push(CameraKeyframe { time: hold_time, ..prev });
                    }
                }
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time,
                    x: cx,
                    y: cy,
                    zoom,
                    easing: Easing::EaseInOut,
                    shake: 0.0,
                    roll: 0.0,
                    pitch,
                });
            }
            CameraStmt::Reset { duration } => {
                let dur = duration.map(|d| d.as_secs()).unwrap_or(0.0);
                self.camera_keyframes.push(CameraKeyframe {
                    time: self.time + dur,
                    x: 0.5,
                    y: 0.5,
                    zoom: 1.0,
                    easing: Easing::EaseInOut,
                    shake: 0.0,
                    roll: 0.0,
                    pitch: 0.0,
                });
                self.time += dur;
            }
        }
        Ok(())
    }

    fn compile_transition(&mut self, tr: &TransitionStmt) -> Result<(), AnimError> {
        let (kind, dur) = match tr {
            TransitionStmt::FadeBlack(d) => (TransitionKind::FadeBlack, d.as_secs()),
            TransitionStmt::FadeWhite(d) => (TransitionKind::FadeWhite, d.as_secs()),
            TransitionStmt::Cut => (TransitionKind::Cut, 0.0),
            TransitionStmt::Dissolve(d) => (TransitionKind::Dissolve, d.as_secs()),
            TransitionStmt::Static(d) => (TransitionKind::Static, d.as_secs()),
            TransitionStmt::Invert(d) => (TransitionKind::Invert, d.as_secs()),
            TransitionStmt::Wipe {
                direction,
                duration,
            } => (TransitionKind::Wipe(*direction), duration.as_secs()),
        };

        self.transitions.push(TransitionEvent {
            time: self.time,
            kind,
            duration: dur,
        });

        self.time += dur;
        Ok(())
    }

    // -----------------------------------------------------------------------
    // Keyframe helpers
    // -----------------------------------------------------------------------

    fn ensure_current_keyframe(&mut self, entity: &str, property: Property) {
        // Read the current value first, before borrowing tracks mutably.
        let value = self.get_entity_property(entity, property);
        let time = self.time;

        let props = self
            .tracks
            .entry(entity.to_string())
            .or_insert_with(HashMap::new);
        let keyframes = props.entry(property).or_insert_with(Vec::new);

        if keyframes.is_empty() {
            keyframes.push(Keyframe {
                time,
                value,
                easing: Easing::Linear,
            });
            return;
        }

        // ХОЛД ДО ТЕКУЩЕГО МОМЕНТА. Раньше здесь не делалось НИЧЕГО, если
        // дорожка уже не пуста, — и вторая анимация того же свойства тянулась
        // от ПРЕДЫДУЩЕГО ключа через весь разрыв. Очки в «Теориях личности»
        // прятались на 3-й секунде и показывались на 29-й: вместо мгновенного
        // появления движок 26 секунд плавно проявлял их посреди кадра, и
        // призрачная пара висела рядом с головой всю первую половину ролика.
        // Тот же класс ошибки, что «плавный наезд вместо склейки» у камеры:
        // там он уже лечился холдом, здесь — нет. Пришпиливаем текущее
        // значение к текущему времени, тогда следующий ключ отрабатывает свою
        // длительность, а не длительность паузы перед ним.
        let last = keyframes[keyframes.len() - 1].clone();
        if last.time < time - 1e-9 {
            keyframes.push(Keyframe {
                time,
                value: last.value,
                easing: Easing::Linear,
            });
        }
    }

    fn add_keyframe(
        &mut self,
        entity: &str,
        property: Property,
        time: f64,
        value: f64,
        easing: Easing,
    ) {
        let props = self
            .tracks
            .entry(entity.to_string())
            .or_insert_with(HashMap::new);
        let keyframes = props.entry(property).or_insert_with(Vec::new);
        keyframes.push(Keyframe {
            time,
            value,
            easing,
        });
    }

    fn set_keyframe(
        &mut self,
        entity: &str,
        property: Property,
        time: f64,
        value: f64,
        easing: Easing,
    ) {
        let props = self
            .tracks
            .entry(entity.to_string())
            .or_insert_with(HashMap::new);
        let keyframes = props.entry(property).or_insert_with(Vec::new);
        keyframes.push(Keyframe {
            time,
            value,
            easing,
        });
    }

    fn get_entity_property(&self, entity: &str, property: Property) -> f64 {
        if let Some(e) = self.entities.get(entity) {
            match property {
                Property::X => e.x,
                Property::Y => e.y,
                Property::ScaleX => e.scale_x,
                Property::ScaleY => e.scale_y,
                Property::Rotation => e.rotation,
                Property::Opacity => e.opacity,
            }
        } else {
            match property {
                Property::Opacity => 1.0,
                Property::ScaleX | Property::ScaleY => 1.0,
                _ => 0.0,
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Evaluation — sample the timeline at a given time `t`
// ---------------------------------------------------------------------------

/// Evaluate a single property track at time `t`.
pub fn evaluate_track(track: &Track, t: f64) -> f64 {
    let kfs = &track.keyframes;
    if kfs.is_empty() {
        return 0.0;
    }
    if kfs.len() == 1 || t <= kfs[0].time {
        return kfs[0].value;
    }
    if t >= kfs.last().unwrap().time {
        return kfs.last().unwrap().value;
    }

    // Find the two surrounding keyframes.
    for i in 0..kfs.len() - 1 {
        if t >= kfs[i].time && t < kfs[i + 1].time {
            let dt = kfs[i + 1].time - kfs[i].time;
            if dt == 0.0 {
                return kfs[i + 1].value;
            }
            let progress = (t - kfs[i].time) / dt;
            let eased = apply_easing(progress, kfs[i + 1].easing);
            return lerp(kfs[i].value, kfs[i + 1].value, eased);
        }
    }

    kfs.last().unwrap().value
}

/// Evaluate the camera state at time `t`.
pub fn evaluate_camera(camera_track: &CameraTrack, t: f64) -> CameraKeyframe {
    let kfs = &camera_track.keyframes;
    if kfs.is_empty() {
        return CameraKeyframe {
            time: t,
            x: 0.5,
            y: 0.5,
            zoom: 1.0,
            easing: Easing::Linear,
            shake: 0.0,
            roll: 0.0,
            pitch: 0.0,
        };
    }
    if kfs.len() == 1 || t <= kfs[0].time {
        return kfs[0].clone();
    }
    if t >= kfs.last().unwrap().time {
        return kfs.last().unwrap().clone();
    }

    for i in 0..kfs.len() - 1 {
        if t >= kfs[i].time && t < kfs[i + 1].time {
            let dt = kfs[i + 1].time - kfs[i].time;
            if dt == 0.0 {
                return kfs[i + 1].clone();
            }
            let progress = (t - kfs[i].time) / dt;
            let eased = apply_easing(progress, kfs[i + 1].easing);
            return CameraKeyframe {
                time: t,
                x: lerp(kfs[i].x, kfs[i + 1].x, eased),
                y: lerp(kfs[i].y, kfs[i + 1].y, eased),
                zoom: lerp(kfs[i].zoom, kfs[i + 1].zoom, eased),
                easing: kfs[i + 1].easing,
                shake: lerp(kfs[i].shake, kfs[i + 1].shake, eased),
                roll: lerp(kfs[i].roll, kfs[i + 1].roll, eased),
                pitch: lerp(kfs[i].pitch, kfs[i + 1].pitch, eased),
            };
        }
    }

    kfs.last().unwrap().clone()
}

/// Check for character overlaps throughout a timeline.
/// Returns an error if any two characters overlap at any point.
///
/// Characters are sampled at 0.1s intervals. Two characters overlap if their
/// horizontal bounding boxes intersect (based on a base width of 0.12, scaled
/// by `scale_x`) AND they are on a similar vertical plane (within 0.15).
/// Characters that are offscreen or nearly invisible are excluded.
pub fn check_overlaps(
    timeline: &Timeline,
    initial_entities: &HashMap<String, EntityState>,
    character_names: &[String],
) -> Result<(), AnimError> {
    const BASE_WIDTH: f64 = 0.12;
    const Y_THRESHOLD: f64 = 0.15;
    const OPACITY_THRESHOLD: f64 = 0.01;
    const TIME_STEP: f64 = 0.1;

    if character_names.len() < 2 {
        return Ok(());
    }

    // Build a lookup: for each character, find the tracks for X, Y, Opacity, ScaleX.
    struct CharTracks<'a> {
        x: Option<&'a Track>,
        y: Option<&'a Track>,
        opacity: Option<&'a Track>,
        scale_x: Option<&'a Track>,
    }

    let mut char_tracks: HashMap<&str, CharTracks> = HashMap::new();
    for name in character_names {
        char_tracks.insert(
            name.as_str(),
            CharTracks {
                x: None,
                y: None,
                opacity: None,
                scale_x: None,
            },
        );
    }

    for track in &timeline.tracks {
        if let Some(ct) = char_tracks.get_mut(track.entity.as_str()) {
            match track.property {
                Property::X => ct.x = Some(track),
                Property::Y => ct.y = Some(track),
                Property::Opacity => ct.opacity = Some(track),
                Property::ScaleX => ct.scale_x = Some(track),
                _ => {}
            }
        }
    }

    // Helper to get a property value at time t, falling back to initial state.
    let get_value = |name: &str, tracks: &CharTracks, prop: Property, t: f64| -> f64 {
        let track_opt = match prop {
            Property::X => tracks.x,
            Property::Y => tracks.y,
            Property::Opacity => tracks.opacity,
            Property::ScaleX => tracks.scale_x,
            _ => None,
        };
        if let Some(track) = track_opt {
            evaluate_track(track, t)
        } else if let Some(entity) = initial_entities.get(name) {
            match prop {
                Property::X => entity.x,
                Property::Y => entity.y,
                Property::Opacity => entity.opacity,
                Property::ScaleX => entity.scale_x,
                _ => 0.0,
            }
        } else {
            match prop {
                Property::Opacity | Property::ScaleX => 1.0,
                _ => 0.5,
            }
        }
    };

    // Sample through time.
    let num_steps = ((timeline.duration / TIME_STEP).ceil() as usize).max(1);
    for step in 0..=num_steps {
        let t = (step as f64 * TIME_STEP).min(timeline.duration);

        // Collect visible, on-screen character positions.
        struct CharPos {
            name: String,
            x: f64,
            y: f64,
            half_width: f64,
        }

        let mut visible_chars: Vec<CharPos> = Vec::new();

        for name in character_names {
            let tracks = &char_tracks[name.as_str()];

            let opacity = get_value(name, tracks, Property::Opacity, t);
            if opacity < OPACITY_THRESHOLD {
                continue;
            }

            let x = get_value(name, tracks, Property::X, t);
            let y = get_value(name, tracks, Property::Y, t);

            // Skip offscreen characters.
            if x < -0.1 || x > 1.1 {
                continue;
            }

            let scale_x = get_value(name, tracks, Property::ScaleX, t);
            let half_width = (BASE_WIDTH * scale_x) / 2.0;

            visible_chars.push(CharPos {
                name: name.clone(),
                x,
                y,
                half_width,
            });
        }

        // Check all pairs.
        for i in 0..visible_chars.len() {
            for j in (i + 1)..visible_chars.len() {
                let a = &visible_chars[i];
                let b = &visible_chars[j];

                let dx = (a.x - b.x).abs();
                let dy = (a.y - b.y).abs();
                let min_x_dist = a.half_width + b.half_width;

                if dx < min_x_dist && dy < Y_THRESHOLD {
                    return Err(AnimError::Overlap(format!(
                        "Character overlap detected at t={:.1}s: '{}' and '{}' are at positions \
                         ({:.2}, {:.2}) and ({:.2}, {:.2}) which are too close \
                         (distance: {:.2}, minimum: {:.2})",
                        t, a.name, b.name, a.x, a.y, b.x, b.y, dx, min_x_dist,
                    )));
                }
            }
        }
    }

    Ok(())
}

fn lerp(a: f64, b: f64, t: f64) -> f64 {
    a + (b - a) * t
}

fn apply_easing(t: f64, easing: Easing) -> f64 {
    match easing {
        Easing::Linear => t,
        Easing::EaseIn => t * t,
        Easing::EaseOut => 1.0 - (1.0 - t) * (1.0 - t),
        Easing::EaseInOut => {
            if t < 0.5 {
                2.0 * t * t
            } else {
                1.0 - (-2.0 * t + 2.0).powi(2) / 2.0
            }
        }
    }
}
