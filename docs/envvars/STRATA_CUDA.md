# `STRATA_CUDA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`terminal/setup.py` の `--cuda` オプションの既定値を与え、モデルのセットアップ時に選ぶ NVIDIA エンジンの CUDA Toolkit 世代を指定する。環境変数自体を engine が読む実装は見つからず、engine の実行時カーネルや計算を直接切り替えるものではない。セットアップでは CUDA 12 または 13 の ready-made engine を選ぶか、その世代を指定してビルドし、選択したエンジンをモデルの構成に保存する（`terminal/setup.py:11328-11331`, `9513-9547`, `terminal/strata_control/setup_config.py:433-437`）。

## 値と判定

`argparse` の `--cuda` 引数の既定値に `os.environ.get("STRATA_CUDA") or None` を渡す。未設定と空文字は `None` となり自動選択になる。空白は除去されないため、たとえば `" 12"` は無効。空でない値は `12`、`13`、`auto` のいずれかに一致する必要があり、`true`、`1`、`0`、`12x`、大文字などは選択肢外として引数エラーになる（`terminal/setup.py:11328-11331`, `11385`）。

| 条件 | unset / 空文字 | 有効値 | 無効値 |
| --- | --- | --- | --- |
| `terminal/setup.py` の共通 NVIDIA セットアップ | 自動選択。対象モデルで使う NVIDIA GPU のうち最も古い compute capability が sm_75 未満なら CUDA 12、そうでなければ通常 CUDA 13。CUDA 13 の最低 driver 未満かつ CUDA 12 の互換下限以上なら CUDA 12 | `12`: CUDA 12 を強制、`13`: CUDA 13 を強制、`auto`: 自動選択 | 空白を含む値、`true`、`false`、`1`、`0`、`12x` 等。argparse が有効な選択肢を示す usage error で終了 |

コード上、CUDA 13 の最低 compute capability は sm_75、最低 driver は 580。CUDA 12 に切り替える driver 下限は Windows 528、その他の OS では 525 であり、それ未満はセットアップが `fail(...)` で停止する（`terminal/setup.py:287-299`, `2091-2109`, `11673-11680`）。`--cuda` を明示すると環境変数の既定値を上書きする。値が `auto` の場合も明示値として扱われ、保存済みの CUDA 12 選択を引き継がない（`terminal/setup.py:11328`, `11495-11496`）。

## 有効になる条件

- CUDA 世代の選択は共通の NVIDIA セットアップ経路で行う。AMD/HIP 経路では `cuda_tk` は使われず、Intel SYCL と macOS の専用セットアップ分岐も NVIDIA の共通選択より前に処理される（`terminal/setup.py:11407-11417`, `11595-11600`, `11673-11683`）。
- 自動選択では、そのモデルが使う全 GPU の arch が考慮される。sm_75 未満の GPU があれば CUDA 12、なければ CUDA 13。arch による切替がなければ driver が CUDA 13 の最低値（580）未満でも、CUDA 12 の下限（Windows 528 / その他 525）以上なら CUDA 12 が選ばれる（`terminal/setup.py:2091-2109`, `11668-11680`）。
- `12` または `13` の強制指定は自動判定を上書きする。sm_75 未満の GPU に `13` を指定してもセットアップは選択を拒まず、CUDA 13 にその GPU 用コードがなく engine が動かない旨を警告する。`12` 指定時は CUDA 12 用 driver 下限で判定される（`terminal/setup.py:2091-2109`, `11673-11684`）。
- 前の構成を引き継ぐ場合、環境または CLI から CUDA 値が与えられず (`a.cuda is None`)、前の構成が CUDA 12 なら `12` が引き継がれる。`STRATA_CUDA=auto` や `13` はこの引き継ぎを抑止する（`terminal/setup.py:11479-11496`）。
- rollback 経路でも `a.cuda == "12"` なら CUDA 12、その他の値なら CUDA 13 の engine を戻す。従って環境変数の値も `--rollback-engine` の選択に影響する（`terminal/setup.py:11471-11472`）。

## 実行時の詳細

値は `terminal/setup.py` の CLI parser 構築時に一度読み込まれ、parse 後は `a.cuda` として扱われる。実行中に環境変数を変えても現在の parser の値は変わらない。プロセスを起動し直すと再読込される（`terminal/setup.py:11328`, `11385`）。

通常の NVIDIA セットアップでは `cuda_choice` が GPU arch、driver、`a.cuda` から toolkit 世代を選び、選択理由を表示する。CUDA 12 なら `engine_step` は toolkit 12 の ready-made engine を探し、ない場合や `--build` 時は toolkit 12 を指定してビルドする。CUDA 13 は標準の ready-made engine / ビルド経路を使う（`terminal/setup.py:2091-2109`, `9513-9547`, `11673-11684`）。

CUDA 12 の選択はモデル構成の `"cuda": 12` として保存され、次回セットアップ時の引き継ぎに使われる。CUDA 13 はこのキーを設定しない（`terminal/setup.py:9898-9903`, `terminal/strata_control/setup_config.py:433-437`）。通常のモデル起動は既に構成に保存された engine 実行ファイルを使い、`STRATA_CUDA` の engine 実行時読み取り箇所は確認できなかった。

## ログと測定値

理由があるときは `CUDA {12|13}: {理由}` を表示する。自動で選ばれた CUDA 12 の理由は成功表示、`--cuda 12` 強制時と CUDA 13 選択時は警告表示になる。たとえば古い arch を含む状態で CUDA 13 を強制すると、理由に `CUDA 13 has no code for sm_<arch>: the engine will not run on that card` が含まれる。driver が選択世代の下限未満なら、`the NVIDIA driver is too old (...)` として停止する（`terminal/setup.py:2097-2109`, `11673-11684`）。無効な文字列は parser の選択肢検証で引数エラーになる（`terminal/setup.py:11328`, `11385`）。

対象変数による性能測定値は該当なし。ソースに `STRATA_CUDA` を読む engine 実装はなく、本変数の直接効果はセットアップ時の engine 世代選択である。

## 根拠

- `terminal/setup.py:11328-11331` — 環境値を `--cuda` 既定値として読み、許容値を定義。
- `terminal/setup.py:2032-2049`, `2091-2109` — 古い GPU の opt-in と CUDA 世代判定。
- `terminal/setup.py:11471-11496`, `11560-11570`, `11668-11684` — rollback、保存構成の引き継ぎ、NVIDIA 選択・driver 判定。
- `terminal/setup.py:9513-9547`, `9898-9903` — engine の取得・ビルドと構成保存。
- `terminal/strata_control/setup_config.py:433-437` — 共通セットアップ構成への CUDA 12 の記録。
