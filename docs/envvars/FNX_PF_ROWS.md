# `FNX_PF_ROWS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX の prompt prefill で、一つの chunk に処理する prompt row 数の上限を指定します。値は `Engine` の構築時に `pf_c_` に設定され、prefill の chunk 分割、関連バッファーの割り当て、prefill 用ジョブ数の計算に使われます。対象は `src/split` の sFNX engine であり、通常の Strata engine の prefill 設定ではありません。sFNX の CUDA/HIP build と、同じ engine を使う CUDA の `split_fnx_run` がこの設定を読みます（`src/split/CMakeLists.txt:65-80,92-123,153-165`）。

## 値と判定

環境変数が未設定なら既定値は `4096` です。設定されている場合は共通 helper `env_int` が値全体を 10 進の符号付き整数として読みます。許容範囲は `MAXT` 以上 `8192` 以下、かつ `MAXT` の倍数です。この build の `MAXT` は 16 なので、許容値は 16 から 8192 までの 16 の倍数です。

| 入力 | 結果 |
| --- | --- |
| 未設定 | `4096` を使用 |
| `16`〜`8192` の範囲内で 16 の倍数 | 指定値を使用 |
| `+16` など、符号付きの整数全体 | 整数として受理後、同じ範囲検査を適用 |
| 空文字、空白を含む値、小数、末尾に文字がある値、整数でない値、`long long` の範囲外 | `env_int` が `FNX_PF_ROWS: '<値>' is not a whole number` を投げる |
| 整数として読めるが範囲外、または 16 の倍数でない値 | `FNX_PF_ROWS: a multiple of 16 from 16 to 8192, got <値>` を投げる |

値全体を `strtoll` で検査し、後続文字を許しません。先頭・末尾の空白も受理しません。符号は受け付けますが、負数は範囲検査で拒否されます。無効値に対する fallback や clamp はありません。既定値の設定源は `Engine` 内の `pf_c_ = 4096` のみで、CLI 引数による上書きはこの読み取り経路にはありません（`src/split/src/env.hpp:15-22,33-40`; `src/split/src/model.hpp:43`; `src/split/src/engine.hpp:345-348`; `src/split/src/engine.cu:62-66`）。

## 有効になる条件

- sFNX split engine を使うプロセスで有効です。sFNX の engine は CMake で CUDA または HIP としてビルドされます。`split_fnx_run` は同じ engine ソースを使う CUDA の実行ファイルです（`src/split/CMakeLists.txt:65-80,92-123,153-165`）。
- engine 構築時に一度だけ読みます。設定はその `Engine` インスタンスに固定され、プロセス実行中に環境を書き換えても既存 engine の値は変わりません。別の engine を後から構築する場合は、その構築時点の値が読まれます（`src/split/src/engine.cu:31,62-69`）。
- sFNX サーバーではモデルと MTP を読み込んだ後、engine を構築する時点で判定されます（`src/split/tools/sfnx.cpp:1050-1061`）。
- 別の環境変数や CLI 値との優先順位分岐はありません。行数の有効範囲を満たさなければ engine 構築自体が失敗します。

## 実行時の詳細

`Engine` の構築時に `FNX_PF_ROWS` を `env_int` で読み、範囲検査後 `pf_c_` に格納します。その値から `pf_jobs_` を計算し、`set_prompt_rows(pf_c_)` に渡します（`src/split/src/engine.cu:62-69`）。prefill は `pf_c_` ごとに token を chunk 化します。最後の chunk は残り token 数に応じて短くなります。複数 chunk の pass 幅は `K * pf_c_` です（`src/split/src/prefill.cu:1004-1028`）。関連する device/host バッファーも `pf_c_` を基準に確保されます（例: `src/split/src/prefill.cu:652-666,995-1002`）。

sFNX からの起動では、値が不正だと engine の構築が例外で失敗します。サーバー経路は `ERR <理由>` を出力し、stderr に `sfnx: failed: <理由>` を出して終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1027-1035,1055-1061`）。したがって行数の設定はプロンプト要求ごとではなく、サーバー起動時に作られる engine 全体に適用されます。

## 根拠

- 読み取り、範囲検査、engine 内の設定: `src/split/src/engine.cu:31-69`
- 数値の全体 parse と未設定時 default: `src/split/src/env.hpp:15-22,33-40`; `src/split/src/engine.hpp:345-348`
- `MAXT=16`: `src/split/src/model.hpp:43`
- chunk 分割と pass 幅: `src/split/src/prefill.cu:1004-1028`
- sFNX の CUDA/HIP build と `split_fnx_run`: `src/split/CMakeLists.txt:65-80,92-123,153-165`
- sFNX の engine 構築と失敗出力: `src/split/tools/sfnx.cpp:1027-1035,1050-1061`

`src/split/src/engine.hpp:345-347` のコメントも既定値 4096 と上限 8192 を記載しています。`docs/DETAILS.md` には `FNX_PF_ROWS` の説明は見当たりません。コメントにある性能値は条件が十分記されていないため、本書では性能効果として断定していません。
