# `STRATA_Q36_CHUNK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen3.6-35B-A3B 用 `strata-q36` エンジンが自動で選ぶ prompt chunk（1 回の forward step で処理する prompt token 数）を、指定値で上書きします。通常は利用可能な GPU メモリ、expert の配置、slot 数などから選ばれる値を固定できます。変更するのは prompt の分割幅であり、環境変数自体はモデル、context、KV cache の幅を変更しません。実装は `engine/src/qwen35/q36_engine.cu` の `strata::qwen35::run` です（同ファイル:5339-5347, 5475-5522）。

## 値と判定

環境変数は `std::getenv` で設定有無を見て、設定されていれば値全体の検証なしに `std::atoi` へ渡し、その結果を 256〜4096 に clamp します。`atoi` は先頭の空白と符号を許し、先頭の十進数字列までを変換し、後続文字を無視します。数字として読めない場合（空文字を含む）は 0 となり、下限の 256 になります。大文字小文字を調べる文字列判定はありません（同ファイル:5517）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値・例 |
|---|---|---|---|
| `chunk == 0`（既定値、または CLI で `--chunk 0` / `--prefill auto`） | GPU メモリ等に基づく自動選択値 | `256`〜`4096` はその値。`512tail` は 512、`+1024` は 1024 | 空文字、`abc`、`0`、`-1`、`255`、`0anything` は 256 に clamp。`4097` は 4096 に clamp。空白だけも 256 |
| `chunk != 0`（CLI の `--chunk N` / `--prefill N`） | CLI 指定値 | この変数は参照されず CLI 指定値が使われる | 同左。環境変数の内容は判定されない |

明示的な CLI 値は `std::atoi` で読み、`auto` だけが 0 になります。CLI 値は環境変数の clamp と異なり、後段の検査で負数または 4096 超過なら `bad --chunk / --max-context` を stderr に出して終了コード 2 になります。CLI 引数を複数回指定した場合は最後の指定が残ります（同ファイル:5348-5364, 5456-5457）。

## 有効になる条件

- `strata-q36` の実行、または `strata` が Qwen3.6 (`qwen35moe`) モデルを同じエンジンへ切り替えて実行する経路で有効です（`engine/src/qwen35/q36_main.cpp:1-5`; `engine/cmake/strata_gpu_engine.cmake:565-584`）。
- CUDA または HIP の GPU engine build が必要です。`strata_qwen35` は HIP gfx906 build では作られず、CUDA/HIP 共通 GPU engine の外（SYCL 等）ではこの読み取り箇所は実行されません（`engine/cmake/strata_gpu_engine.cmake:1-8,565-584`）。
- CLI の `--chunk` / `--prefill` が既定の 0 または `auto` のときだけ環境変数の値が使われます。正の CLI chunk は環境変数より優先します。自動値を算出した後に環境変数値を代入するため、自動選択時の VRAM 空き量や expert 配置の判定結果は上書きされます（`engine/src/qwen35/q36_engine.cu:5362-5364,5475-5517`）。
- モデルをロードできない場合は chunk 選択処理に到達せず、環境変数も読みません（同ファイル:5458-5464,5475-5522）。
- `STRATA_Q36_PLACE_DEBUG` が設定されている場合に限り、選択済み chunk を含む `strata-q36: chunk rule: ...` の stderr 行が出ます。この診断変数が未設定なら、その行は出ません（同ファイル:5518-5520）。

## 実行時の詳細

引数解析時点では `chunk` の初期値は 0 です。`--chunk` または `--prefill` は数値を `atoi` で読み、文字列 `auto` の場合に 0 を設定します。モデルのロード後、`chunk == 0` のときだけ CUDA の空きメモリとモデル内の expert サイズ等から自動値を決め、その直後に `STRATA_Q36_CHUNK` を 1 回読み、設定済みなら値を上書きします。関数内 static cache やリクエストごとの再読込はありません。選択した値は `E.init(m, ctx, chunk, ...)` に渡り、prompt は `tmax` token 以下の単位で処理されます（同ファイル:5342,5348-5364,5458-5522,1962-1969,3720-3747）。

この読み取り箇所からは環境変数値によるエラー終了や警告はありません。変換後の値は clamp されてから engine に渡ります。起動時に一度読むため、その後プロセス環境を変えても選択済み chunk には反映されません。chunk の実値は通常の初期化ログ `strata-q36: context ... prompt chunk ...` に出ます（同ファイル:2254-2259）。

## ログと測定値

`STRATA_Q36_PLACE_DEBUG` も設定されていると、stderr に `strata-q36: chunk rule: free ... GiB (raw ..., with ... packed), main experts ... GiB, chunk %d` が出て、この変数による上書き後の chunk を確認できます。通常の初期化 stderr 行にも `prompt chunk %d` が出ます。環境変数別の測定値はソースから確認できません（`engine/src/qwen35/q36_engine.cu:5517-5520,2254-2259`）。

## 根拠

- 候補名の全参照を現行 checkout で `rg` 検索し、実コードで値を読む箇所は `engine/src/qwen35/q36_engine.cu:5517` の 1 箇所と確認しました。docs・settings registry の記載は実装根拠にしていません。
- 初期値、引数上書き、CLI の値変換: `engine/src/qwen35/q36_engine.cu:5342,5348-5364`。
- CLI 範囲検査とモデルロード順: `engine/src/qwen35/q36_engine.cu:5456-5464`。
- 自動選択と環境変数上書き、診断ログ、初期化への引き渡し: `engine/src/qwen35/q36_engine.cu:5475-5522`。
- 実際の prompt 分割と初期化ログ: `engine/src/qwen35/q36_engine.cu:1962-1969,2254-2259,3720-3747`。
- 対応 backend / build 条件、standalone と `strata` からの利用: `engine/cmake/strata_gpu_engine.cmake:1-8,565-584`; standalone entry: `engine/src/qwen35/q36_main.cpp:1-5`。
