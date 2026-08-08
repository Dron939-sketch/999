# Каталог локаций

Все локации серии одним списком: превью, линия пола и в каких роликах уже
стоят. Собирается инструментом, а не руками — `python3 tools/katalog.py`.

**Почему тут превью, а не копии SVG.** Копия — это второй файл, который
начинает жить своей жизнью: поправишь оригинал, а в копии останется старое,
и однажды ролик соберётся не с той картинкой. Локации лежат там же, где
лежали, — в `examples/assets/sets/`. Каталог показывает, ЧТО у нас есть,
и не создаёт второй правды.

**Линия пола** — `back_y` из карты поверхностей: где начинается пол. Прочерк
значит, что карты нет и `place ... on floor` на этой локации молча не
сработает: снять карту перед первым использованием.

| Локация | Превью | Пол | Где стоит |
|---|---|---|---|
| `bazaar-obeschanij.svg` | ![bazaar-obeschanij](katalog/bazaar-obeschanij.png) | 0.33 | lektorij-manifest |
| `biznes-street.svg` | ![biznes-street](katalog/biznes-street.png) | 0.66 | lektorij-manifest, biznes-myshlenie-intro |
| `book-title-page.svg` | ![book-title-page](katalog/book-title-page.png) | — | pereproshivka-intro |
| `cafe-ruins.svg` | ![cafe-ruins](katalog/cafe-ruins.png) | 0.667 | — |
| `card-biznes.svg` | ![card-biznes](katalog/card-biznes.png) | — | biznes-myshlenie-intro |
| `card-l1.svg` | ![card-l1](katalog/card-l1.png) | — | — |
| `card-title.svg` | ![card-title](katalog/card-title.png) | — | — |
| `cherdak.svg` | ![cherdak](katalog/cherdak.png) | 0.472 | istoriya-religij |
| `derevo-pen.svg` | ![derevo-pen](katalog/derevo-pen.png) | 0.403 | istoriya-religij |
| `detskaya.svg` | ![detskaya](katalog/detskaya.png) | 0.764 | istoriya-religij |
| `doors-empty.svg` | ![doors-empty](katalog/doors-empty.png) | 0.597 | myshlenie-intro, lektorij-manifest |
| `doroga-stolby.svg` | ![doroga-stolby](katalog/doroga-stolby.png) | 0.38 | distanciya |
| `dva-stula.svg` | ![dva-stula](katalog/dva-stula.png) | 0.347 | privyazannost |
| `dve-tropy.svg` | ![dve-tropy](katalog/dve-tropy.png) | 0.118 | privyazannost |
| `field-day.svg` | ![field-day](katalog/field-day.png) | — | — |
| `field-emblem.svg` | ![field-emblem](katalog/field-emblem.png) | — | — |
| `field-empty.svg` | ![field-empty](katalog/field-empty.png) | 0.681 | teorii-lichnosti-intro, lektorij-manifest, insight-proverka, kak-dumat-intro, snova-zhivoj-intro |
| `freeman-stage.svg` | ![freeman-stage](katalog/freeman-stage.png) | — | etalon-15s |
| `kamen-memento.svg` | ![kamen-memento](katalog/kamen-memento.png) | 0.444 | istoriya-religij |
| `kuhnya-chajnik-tiho.svg` | ![kuhnya-chajnik-tiho](katalog/kuhnya-chajnik-tiho.png) | 0.56 | emocii |
| `kuhnya-chajnik.svg` | ![kuhnya-chajnik](katalog/kuhnya-chajnik.png) | 0.56 | emocii |
| `kuhnya-noch.svg` | ![kuhnya-noch](katalog/kuhnya-noch.png) | 0.431 | privyazannost |
| `kuhnya-schet.svg` | ![kuhnya-schet](katalog/kuhnya-schet.png) | 0.47 | distanciya |
| `lektorij-final.svg` | ![lektorij-final](katalog/lektorij-final.png) | — | prison-intro, vliyanie, istoriya-religij, photoshock-demo, distanciya, myshlenie-intro, teorii-lichnosti-intro, lektorij-manifest, privyazannost, insight-proverka, emocii, kak-dumat-intro, final-titry, snova-zhivoj-intro |
| `lektorij-paper.svg` | ![lektorij-paper](katalog/lektorij-paper.png) | — | lekciya-2-frejd-psihodinamika, fredi-lecture-template, fredi-expressions-demo |
| `lektorij-zal.svg` | ![lektorij-zal](katalog/lektorij-zal.png) | 0.62 | vliyanie, istoriya-religij, distanciya, lektorij-manifest, privyazannost, emocii |
| `mind-alive.svg` | ![mind-alive](katalog/mind-alive.png) | — | pereproshivka-intro |
| `paper.svg` | ![paper](katalog/paper.png) | — | — |
| `perekrestok-bez-znakov.svg` | ![perekrestok-bez-znakov](katalog/perekrestok-bez-znakov.png) | 0.49 | vliyanie |
| `ploschadka-dve-dveri.svg` | ![ploschadka-dve-dveri](katalog/ploschadka-dve-dveri.png) | 0.66 | distanciya |
| `prihozhaya-pakety.svg` | ![prihozhaya-pakety](katalog/prihozhaya-pakety.png) | 0.62 | vliyanie |
| `prison-cell.svg` | ![prison-cell](katalog/prison-cell.png) | 0.655 | prison-intro, pereproshivka-intro |
| `prison-infocygane.svg` | ![prison-infocygane](katalog/prison-infocygane.png) | 0.655 | lektorij-manifest |
| `stol-posle-gostej.svg` | ![stol-posle-gostej](katalog/stol-posle-gostej.png) | 0.45 | vliyanie |
| `supermarket-ryady.svg` | ![supermarket-ryady](katalog/supermarket-ryady.png) | 0.3 | vliyanie |
| `vannaya-zerkalo.svg` | ![vannaya-zerkalo](katalog/vannaya-zerkalo.png) | 0.62 | emocii |
| `void-black.svg` | ![void-black](katalog/void-black.png) | 0.972 | vliyanie, istoriya-religij, distanciya, lektorij-manifest, privyazannost, emocii |
| `void.svg` | ![void](katalog/void.png) | — | pereproshivka-intro |
| `wasteland.svg` | ![wasteland](katalog/wasteland.png) | — | — |

Всего локаций: **39**.
