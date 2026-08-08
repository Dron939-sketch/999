//! Video pipeline — encodes rendered frames into an MP4 video via FFmpeg.

use std::io::Write;
use std::path::Path;
use std::process::{Command, Stdio};

use crate::errors::AnimError;
use crate::renderer::Frame;

/// Encode a sequence of frames into an MP4 video file.
pub fn encode_video(frames: &[Frame], output: &Path, fps: u32) -> Result<(), AnimError> {
    if frames.is_empty() {
        return Err(AnimError::Video("no frames to encode".into()));
    }

    let width = frames[0].width;
    let height = frames[0].height;

    log::info!(
        "Encoding {} frames to {} ({}x{} @ {} fps)",
        frames.len(),
        output.display(),
        width,
        height,
        fps,
    );

    // Create parent directories if they don't exist.
    if let Some(parent) = output.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent).map_err(|e| {
                AnimError::Video(format!(
                    "failed to create output directory '{}': {e}",
                    parent.display()
                ))
            })?;
        }
    }

    // Spawn FFmpeg process.
    let mut child = Command::new("ffmpeg")
        .args([
            "-y", // overwrite output
            "-f",
            "rawvideo", // input format
            "-pix_fmt",
            "rgba", // input pixel format
            "-s",
            &format!("{width}x{height}"), // frame size
            "-r",
            &fps.to_string(), // frame rate
            "-i",
            "-", // read from stdin
            "-c:v",
            "libx264", // H.264 codec
            "-pix_fmt",
            "yuv420p", // output pixel format
            "-preset",
            "medium", // encoding speed/quality tradeoff
            "-crf",
            "28", // quality (lower = better); film grain is high-entropy, so...
            "-maxrate",
            "2200k", // ...cap the bitrate (VBV) — grain can't blow up file size
            "-bufsize",
            "4400k", // VBV buffer; keeps a 52s clip ~14MB (well under repo limits)
            "-tune",
            "grain", // preserve the intended grain look at the capped bitrate
            "-movflags",
            "+faststart", // optimize for streaming
        ])
        .arg(output.as_os_str())
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| {
            AnimError::Video(format!("failed to start ffmpeg: {e}. Is ffmpeg installed?"))
        })?;

    let stdin = child
        .stdin
        .as_mut()
        .ok_or_else(|| AnimError::Video("failed to open ffmpeg stdin".into()))?;

    // Write each frame's raw RGBA data to FFmpeg's stdin.
    for (i, frame) in frames.iter().enumerate() {
        stdin
            .write_all(&frame.data)
            .map_err(|e| AnimError::Video(format!("failed to write frame {i} to ffmpeg: {e}")))?;
    }

    // Close stdin to signal end of input.
    drop(child.stdin.take());

    // Wait for FFmpeg to finish.
    let output_result = child
        .wait_with_output()
        .map_err(|e| AnimError::Video(format!("ffmpeg process error: {e}")))?;

    if !output_result.status.success() {
        let stderr = String::from_utf8_lossy(&output_result.stderr);
        return Err(AnimError::Video(format!("ffmpeg failed: {stderr}")));
    }

    log::info!("Video encoded successfully: {}", output.display());
    Ok(())
}

/// Encode frames as individual PNG files (useful for debugging).
pub fn encode_png_sequence(frames: &[Frame], output_dir: &Path) -> Result<(), AnimError> {
    std::fs::create_dir_all(output_dir)?;

    for (i, frame) in frames.iter().enumerate() {
        let path = output_dir.join(format!("frame_{:06}.png", i));
        write_png(&path, &frame.data, frame.width, frame.height)?;
    }

    log::info!(
        "Wrote {} PNG frames to {}",
        frames.len(),
        output_dir.display()
    );
    Ok(())
}

fn write_png(path: &Path, data: &[u8], width: u32, height: u32) -> Result<(), AnimError> {
    let file = std::fs::File::create(path)?;
    let w = std::io::BufWriter::new(file);

    let mut encoder = png::Encoder::new(w, width, height);
    encoder.set_color(png::ColorType::Rgba);
    encoder.set_depth(png::BitDepth::Eight);

    let mut writer = encoder
        .write_header()
        .map_err(|e| AnimError::Render(format!("PNG header error: {e}")))?;

    writer
        .write_image_data(data)
        .map_err(|e| AnimError::Render(format!("PNG write error: {e}")))?;

    Ok(())
}

// ─────────────────────────────────────────────────────────────────────────────
// ПОТОКОВЫЙ КОДЕР: кадр отдаётся ffmpeg сразу и тут же забывается.
//
// ПОЧЕМУ ОН ПОЯВИЛСЯ. `encode_video` берёт `&[Frame]` — то есть ВСЕ кадры
// ролика, уже лежащие в памяти. Кадр 1280×720 в RGBA весит 3.69 МБ, и до сих
// пор это сходило с рук: ролики шли по 90 секунд, это 2200 кадров и 8 ГБ —
// впритык, но помещалось в 16 ГБ раннера.
//
// Ролик на 3:41 — это 5300 кадров и 19.5 ГБ. Раннер убил процесс на пятой
// минуте рендера: «The runner has received a shutdown signal». Ни строчки про
// память в логе нет, и в этом главная подлость — падение выглядит как сбой
// инфраструктуры, а не как переполнение.
//
// ЧТО ЗДЕСЬ ВМЕСТО НАКОПЛЕНИЯ. ffmpeg запускается ОДИН РАЗ в начале рендера, и
// каждый готовый кадр уходит ему в stdin сразу после постобработки. В памяти
// живёт ровно одна сцена, а не весь ролик; после отдачи кадры сцены
// освобождаются. Потолок длины ролика этим снимается совсем: 3 минуты, 10
// минут и час стоят одинаково.
//
// Постобработка от этого не страдает: все её проходы (`monochrome`,
// `line_boil`, `film`, `filmstock`, `snow`) считаются ПОКАДРОВО и зависят
// только от номера кадра. Номер поэтому и передаётся сквозным — `Koder`
// считает отданные кадры сам, а вызывающая сторона обязана применять
// постобработку до `push`.
pub struct Koder {
    child: std::process::Child,
    png_dir: Option<std::path::PathBuf>,
    otdano: usize,
    width: u32,
    height: u32,
}

impl Koder {
    /// Запускает ffmpeg и ждёт кадры. `png_dir` — необязательная выгрузка
    /// последовательности PNG тем же потоком.
    pub fn start(
        output: &Path,
        width: u32,
        height: u32,
        fps: u32,
        png_dir: Option<&Path>,
    ) -> Result<Self, AnimError> {
        if let Some(parent) = output.parent() {
            if !parent.as_os_str().is_empty() {
                std::fs::create_dir_all(parent).map_err(|e| {
                    AnimError::Video(format!(
                        "failed to create output directory '{}': {e}",
                        parent.display()
                    ))
                })?;
            }
        }
        if let Some(dir) = png_dir {
            std::fs::create_dir_all(dir)?;
        }

        log::info!(
            "Streaming encode to {} ({}x{} @ {} fps)",
            output.display(),
            width,
            height,
            fps
        );

        let child = Command::new("ffmpeg")
            .args([
                "-y",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgba",
                "-s",
                &format!("{width}x{height}"),
                "-r",
                &fps.to_string(),
                "-i",
                "-",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "medium",
                "-crf",
                "28",
                "-maxrate",
                "2200k",
                "-bufsize",
                "4400k",
                "-tune",
                "grain",
                "-movflags",
                "+faststart",
            ])
            .arg(output.as_os_str())
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| {
                AnimError::Video(format!("failed to start ffmpeg: {e}. Is ffmpeg installed?"))
            })?;

        Ok(Koder {
            child,
            png_dir: png_dir.map(|p| p.to_path_buf()),
            otdano: 0,
            width,
            height,
        })
    }

    /// Отдаёт один ГОТОВЫЙ кадр (постобработка уже применена).
    pub fn push(&mut self, frame: &Frame) -> Result<(), AnimError> {
        if frame.width != self.width || frame.height != self.height {
            return Err(AnimError::Video(format!(
                "frame {} is {}x{}, encoder started as {}x{}",
                self.otdano, frame.width, frame.height, self.width, self.height
            )));
        }
        if let Some(dir) = &self.png_dir {
            let path = dir.join(format!("frame_{:06}.png", self.otdano));
            write_png(&path, &frame.data, frame.width, frame.height)?;
        }
        let stdin = self
            .child
            .stdin
            .as_mut()
            .ok_or_else(|| AnimError::Video("ffmpeg stdin closed early".into()))?;
        stdin.write_all(&frame.data).map_err(|e| {
            AnimError::Video(format!(
                "failed to write frame {} to ffmpeg: {e}",
                self.otdano
            ))
        })?;
        self.otdano += 1;
        Ok(())
    }

    pub fn kadrov(&self) -> usize {
        self.otdano
    }

    /// Закрывает поток и дожидается ffmpeg. Возвращает число отданных кадров.
    pub fn finish(mut self) -> Result<usize, AnimError> {
        if self.otdano == 0 {
            return Err(AnimError::Video("no frames to encode".into()));
        }
        drop(self.child.stdin.take());
        let out = self
            .child
            .wait_with_output()
            .map_err(|e| AnimError::Video(format!("ffmpeg process error: {e}")))?;
        if !out.status.success() {
            let stderr = String::from_utf8_lossy(&out.stderr);
            return Err(AnimError::Video(format!("ffmpeg failed: {stderr}")));
        }
        log::info!("Video encoded successfully: {} frames", self.otdano);
        Ok(self.otdano)
    }
}
