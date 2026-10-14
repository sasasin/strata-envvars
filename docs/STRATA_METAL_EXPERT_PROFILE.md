# `STRATA_METAL_EXPERT_PROFILE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal backend の SSD expert streaming が作る expert arena の初期配置順を与えるプロファイルファイルのパスです。プロファイル内の順位が高い expert から、使用可能な arena budget に収まる分を先に配置します。これは通常の常駐 Metal 実行には使われません。また CUDA/HIP/SYCL の `--expert-profile` 設定を変更する変数でもありません。

## 値と判定

| 値 | 使用されるパス |
|---|---|
| 未設定 | `STRATA_METAL_DATA_DEFAULT` ビルド定数に `/expert-profile.bin` を連結したパス |
| 設定あり | 環境変数の文字列全体をそのままパスとして使用 |
| 空文字 | 空のパスを使用。`fopen("")` が失敗し、プロファイルなしとして処理 |

値の数値変換、真偽値判定、空白除去、相対パスの補正はありません。設定された相対パスの解決基準をこのコードは変更しません。

ファイルを開けた場合、実装は先頭の4 byte が `STRP` であること、続く5個の `uint32_t` のうち `h[1]` と `h[2]` が実装内の layer 数48、expert 数512と一致することを確認します。その後 `h[4]` 件を上限に `uint16_t` の layer/expert ペアを読み、範囲内かつ重複していないペアだけ順位列に加えます。ファイルを開けない場合は stderr に `strata metal stream: no expert profile at <path>: the arena starts layer-interleaved` を出します。開けてもヘッダー不一致、または有効なペアがない場合はこの警告を出さず、順位列は空のままです。順位列に含まれないペアは後から layer-interleaved 順で補われます。

## 有効になる条件

Metal window の `ExpertStream::wanted()` が streaming を選んだ場合に限り、このパスが使われます。streaming は `STRATA_METAL_STREAM=1` で明示的に有効化できます。`STRATA_METAL_STREAM=0` なら無効です。それ以外（未設定や `auto` など）では、モデル全体と余裕分が常駐 footprint 上限に収まらない場合に有効になります。環境変数自身は streaming の選択には関与しません。

## 実行時の詳細

`Window::stream_arena()` は arena 初期化時にこの変数を読み、得たパスを `ExpertStream::make_arena()` に渡します。`make_arena()` はプロファイルの順位を使って budget 内の slots を埋めます。`min_slots` で確保される各 class の最低 slot 数が先に必要になるため、プロファイルにあるペアがすべて arena に入るとは限りません。プロファイルがない場合や有効な順位が得られない場合は、arena を layer-interleaved 順で埋めます。

読み取りは `stream_arena()` の呼び出しごとで、関数内に static cache はありません。したがって、この呼び出し前に環境変数を変更すれば新しい値が使われます。arena が ready になった後は同じ arena を再初期化しないため、その後に値を変更しても既存 arena の順位は変わりません。この読み取り経路に環境変数の子プロセスへの継承・上書き処理はありません。

## 根拠

- `metal/src/engine/window.cpp:425-432` — Metal window 初期化時に streaming の要否を決め、streaming 時に `ExpertStream` を作成。
- `metal/src/engine/stream.cpp:33-48` — `STRATA_METAL_STREAM` による on/off と、自動判定。
- `metal/src/engine/window.cpp:1016-1019,1127-1128,1176-1201` — arena 初期化経路、環境変数の読み取り、既定パス、`make_arena()` への引き渡し。
- `metal/CMakeLists.txt:119` — `STRATA_METAL_DATA_DEFAULT` を Strata の `data` ディレクトリとして定義。
- `metal/src/engine/stream.cpp:368-409` — プロファイルのオープン、ヘッダーとペアの判定、順位列の補完、budget に応じた配置。
