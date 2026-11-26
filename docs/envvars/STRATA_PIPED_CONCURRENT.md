# `STRATA_PIPED_CONCURRENT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`--batch-groups > 1` の層分割パイプラインで、プロンプトの prefill を専用スレッドに移し、その間も slot の batch window を進める実験的な opt-in である。適用条件を満たすと、読込スレッドと slot window が GPU 上で並行し、通常のパイプライン読込のように slot がプロンプト読込の終了を待たない。主制御は `read_part` 内で行い、各 slot の doorbell を専用スレッドが処理する。プロンプト読込で失敗した場合や batch window が失敗した場合は、そのリクエスト処理が失敗する。`engine/src/program/generate.cpp:21009-21023,21054-21062,21113-21116,21138-21153,21243-21274`。

## 値と判定

主制御は `std::getenv` の結果を `std::atoi(v) != 0` で判定する。未設定は無効、空文字も `atoi` が 0 を返すため無効。文字列全体や真偽語は検証せず、`atoi` が読む数値接頭辞が 0 以外なら有効になる。従って `1`, `-1`, `01`, `1anything` は有効、`0`, `0anything`, `true`, `false`, 空文字、数値として読めない文字列は無効。先頭空白の後の数値も `atoi` の規則で変換される。範囲検証や clamp はない。数値範囲外の文字列に対する `atoi` の結果はこのコードで規定されていない。`engine/src/program/generate.cpp:21024-21030`。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| `engine/src` の主制御（CUDA/HIP 向け実装） | 無効 | `1`, `-1`, `1tail` | 空文字, `0`, `0tail`, `true`, `x` |
| CUDA stream 優先度判定（CUDA build のみ） | この変数が unset なら最高優先度を要求しない | 上記の主制御が有効で、`STRATA_PIPED_CONCURRENT_PRIO` も unset または `atoi` が非 0 | この変数が空文字/0相当、または `STRATA_PIPED_CONCURRENT_PRIO=0` 相当 |

## 有効になる条件

- `--batch` が正、`--batch-groups` が 1 より大きく、層分割 pipeline の stage があること（`piped` 条件）。`engine/src/program/generate.cpp:17529-17533`。
- 画像を含まない prompt であること。prompt の現在の区間長 `b0 - a0` が `STRATA_PIPED_CONCURRENT_MIN` 以上であること。同 MIN は unset/0 なら全長を許し、`atoll` の後に負値を 0 へ clamp する。短い入力は通常の読み込み経路へ進む。`engine/src/program/generate.cpp:21047-21054`。
- 次の競合条件が一つでもあると opt-in は無効になり、stderr に `strata batch: STRATA_PIPED_CONCURRENT is off beside <理由>` を出す。判定順で最初の理由だけを表示する。
  - `STRATA_PREFILL_HELP` の `atoi` が非 0
  - `STRATA_SPLIT_MTP_BATCH` の `atoi` が非 0
  - `STRATA_FS_SLOTS` の `atoi` が非 0
  - `--pcie-mode dma`
  - helper cache が使われる（`--expert-cache-device1..3`、または helper cache を伴う remote expert 経路）
  - 通常の GGUF source が blob staging を使う（GGUF in-place、unbuffered、`STRATA_IO_PREFETCH` 経路）
  - GGUF source と arena source 以外の expert source

  個々の設定値・source 状態から上記条件を組み立てる箇所は `engine/src/program/generate.cpp:21027-21045`、理由名と優先順は `engine/include/strata/program/batch_read.hpp:30-53`。
- `engine/src/program/generate.cpp` にこの読み取り経路があり、同名の読み取りは `engine/sycl/src/program/generate.cpp` にない。CUDA/HIP 向けの当該実装の説明であり、SYCL 実装にこの機能があるとは確認できない。CUDA build では別途 window stream の優先度も変わり得る。HIP ではその優先度分岐を通らず既定の stream priority を使う。`engine/src/core/verify.cpp:1312-1334`。

## 実行時の詳細

`pr_conc` は関数内 `static const bool` で、最初に `read_part` がこの初期化へ到達した時に一度だけ環境を読み、そのプロセス中は結果を cache する。unset と無効値はいずれも false で、CLI 引数による値の上書きはない。別の条件（piped、画像なし、最小 token 数、競合 source/設定）が成立しない場合は通常経路となる。プロセス起動後に環境値を変えても、初期化済みの主判定は変わらない。`verify.cpp` の CUDA 優先度判定も関数内 static で初回 `make_stream` 時に cache される。こちらは `read_part` の他条件が成立しなくても、window stream 作成時に最高優先度を要求し得る。`engine/src/program/generate.cpp:21024-21054`, `engine/src/core/verify.cpp:1312-1318`。

有効経路では必要な MTP prefill buffer を先に reserve し、prompt upload slot も読込前に reserve する。upload slot の reserve に失敗しても警告を出して処理は続ける。読込 thread と doorbell thread を作り、後者が slot window の doorbell を処理する間、メイン側は window の pump と prompt 完了待ちを行う。slot が借りている expert slot は読込前に貸し出し、読込中は window がそれらの expert を CPU で計算し、読込後に補充する。読み込みと slot の別々の stream / memory を使い、prompt による slot 停止を避ける設計である。`engine/src/program/generate.cpp:21054-21062,21113-21175,21218-21226`。

このパスはリクエストごとに `read_part` から選択される一方、環境変数判定自体は static cache される。待機中に短いリクエストの `BYIELD` が届くと、次の chunk で読込を止めて slot に途中分を渡す。失敗した window は `a pipelined batch window failed` として処理失敗になり、prompt reader の例外は `the prompt read failed: ...` または `the prompt read failed` に変換される。`engine/src/program/generate.cpp:21176-21216,21227-21249,21270-21275`。

## ログと測定値

- 不適合条件がある場合: `strata batch: STRATA_PIPED_CONCURRENT is off beside ...`。主判定が off の場合や、pipeline・画像・最小長条件に合わず通常経路へ進む場合、この理由ログは出ない。`engine/src/program/generate.cpp:21041-21045,21054`。
- 有効経路の各 prompt read: `strata batch: read N tokens on a thread of its own in X ms (concurrent, to Q of T); the slots decoded R rows meanwhile (S rows/s; ...)`。予約失敗時は `strata batch: the prompt path's pinned upload slots could not be reserved (they grow at first use)`。`engine/src/program/generate.cpp:21060-21062,21263-21269`。
- CUDA で主変数が有効、かつ `STRATA_PIPED_CONCURRENT_PRIO` が unset または非 0 の場合、window stream の最高優先度作成を試みる。取得または作成に失敗した場合は既定 stream 作成へ fallback し、専用ログはない。HIP / gfx906 系のこの分岐では主変数による優先度要求をしない。`engine/src/core/verify.cpp:1312-1334`。
- Strata の `docs/BATCHING.md:247-281` は実験機能の説明と CUDA/HIP の差を記す。そこに続く性能表は 2x RTX 5090 等の特定構成・計測条件を付したもので、現行 HEAD で再測定した値ではないため、ここでは現行一般性能として扱わない。`docs/BATCHING.md:283-308`。

## 根拠

- `engine/src/program/generate.cpp:17529-17533` — pipelined batch 条件。
- `engine/src/program/generate.cpp:21024-21054` — 主変数の変換、競合判定、最小 prompt 長。
- `engine/include/strata/program/batch_read.hpp:30-53` — 無効化条件と理由の順序。
- `engine/src/program/generate.cpp:21054-21275` — thread、slot/prompt の並行処理、BYIELD、ログ、失敗経路。
- `engine/src/core/verify.cpp:1310-1334` — CUDA window stream 優先度と fallback。
- `engine/sycl/src/program/generate.cpp` — 対象名の読み取りなし。
- `docs/BATCHING.md:247-308` — 設計説明と別条件の測定記録。
