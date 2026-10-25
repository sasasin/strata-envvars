# `STRATA_METAL_MTP_GGUF`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal backend で speculative decoding に使う MTP ドラフト層の GGUF ファイルパスを指定する。`--mtp <runtime-dir>` で MTP を読み込む経路に限り参照される。未設定なら `<runtime-dir>` の親ディレクトリにある `mtp-q2_0.gguf` を既定パスとして使う。

## 値と判定

| 環境変数の状態 | パスの選択と結果 |
| --- | --- |
| 未設定 | `rt_dir` の末尾にある `/` を取り除き、その親ディレクトリに `/mtp-q2_0.gguf` を連結する。`rt_dir` に `/` が含まれない場合は `./mtp-q2_0.gguf`。 |
| 設定済みで非空 | 値全体をファイルパスとして使用する。数値変換や真偽値への変換はなく、パスの存在・形式もこの時点では検証しない。 |
| 設定済みで空文字 | 空のパスを保存する。既定パスには戻らず、decode window 初期化時の MTP GGUF 読み込みをスキップする。ただし `MtpDrafter::load` と Metal の `mtp_load` 自体は成功を返すため、これは上位の `--mtp` 設定を解除する処理ではない。 |

相対パスはそのまま保持され、Strata 側で絶対パス化や正規化は行わない。空白を含む文字列も加工されない。

## 有効になる条件

- `STRATA_GPU_METAL` でビルドされた Metal backend で有効。`src/core/mtp.cpp` はこのビルド条件で Metal engine の `mtp_load` に委譲する。
- `generate` が `--mtp` を受け取り、`--spec T` の `T >= 2` を満たす必要がある。`--mtp` が指定されても `--spec` が2未満なら、`generate.cpp` は `--mtp is ignored without --spec T (T >= 2)` と stderr に出して `--mtp` の値を消し、MTP をロードしない。
- MTP 読み込みが要求されても、GGUF の実ファイル読み込みは decode window 初期化時まで遅延される。環境変数の非空値で指定したファイルを開けない、または GGUF として読み込めない場合、window 初期化が失敗する。
- CUDA/HIP など Metal 以外の `MtpDrafter::load` 実装はこの環境変数を参照しない。

## 実行時の詳細

`generate` は `--mtp` の値が残っている場合に `MtpDrafter::load` を呼ぶ。Metal 実装は受け取った runtime directory と `max_t` を engine に渡す。engine はこの時点で `getenv("STRATA_METAL_MTP_GGUF")` を一度評価し、選んだパスと `max_t` をプロセス内の `g_mtp_path` / `g_mtp_max_t` に保存して成功を返す。

その後、decode window が初めて初期化される際に保存済みのパスを使う。空パスなら `mtp_load_pending` は成功を返して GGUF を開かず、非空なら `Window::mtp_load` がファイルを開いてメモリマップする。ファイルを開けない場合のエラー文字列は `cannot open <path>`、マップ失敗は `mmap failed: <path>`、GGUF magic/version が一致しない場合は `not a GGUF file` / `GGUF version is not 3`。window 初期化の失敗は呼び出し元へ伝播する。

環境変数は MTP の `load` 呼び出し時にパスへコピーされるため、その後の環境変更だけでは保存済みパスは更新されない。MTP をロードしない実行経路では評価されない。空文字を指定して GGUF 読み込みを飛ばしても、上位層が `--mtp` を有効のまま扱う経路は残る。Metal window の `mtp_prefill` / `mtp_draft` は MTP が未ロードの場合 `metal mtp: not loaded` を返すため、空文字での利用は MTP の正常な無効化手段として扱えない。

## 文書との照合

`docs/ORCA.md` は MTP GGUF を `tools/mtp_pack.py` で `<mtp-dir>/mtp-q2_0.gguf` に作成し、`tools/mtp_rt.py` で runtime directory を生成する手順を記載している（33–41行）。これはソースの既定配置 `<rt>/../mtp-q2_0.gguf` と整合する。一方、この文書では `STRATA_METAL_MTP_GGUF` の説明を確認できなかったため、環境変数の意味は実装から記述した。

## 根拠

- `src/program/generate.cpp:4612-4616,4629`: `--mtp` と `--spec` の条件、および MTP load 呼び出し。
- `src/core/mtp.cpp:249-257`: Metal ビルドで Metal engine に委譲する分岐。
- `metal/src/engine/window.cpp:2521-2541`: 環境変数の読み取り、未設定時の既定パス、パスの保存、遅延ロードのスキップ条件。
- `metal/src/engine/window.cpp:2474-2482`: decode window 初期化時に保留中の MTP を読み込む箇所。
- `metal/src/engine/window.cpp:1489-1494,1859-1861,1906-1909`: GGUF を開く処理と、MTP 未ロード時の prefill / draft エラー。
- `metal/src/gguf_lite.cpp:58-72`: open、mmap、GGUF magic/version のエラー処理。
- `docs/ORCA.md:33-41`: MTP GGUF と runtime directory の作成手順。
