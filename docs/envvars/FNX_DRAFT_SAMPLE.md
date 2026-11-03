# `FNX_DRAFT_SAMPLE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。対象は Strata 所有ソース。外部ライブラリの動作は含めない。

## 役割

sFNX split engine の MTP draft token を、draft head の argmax で固定するか、draft head が出す候補とサンプリング設定から抽選するかを切り替えます。未設定時はサンプリング draft が有効です。ただし通常の `Session::generate()` では、sampling が有効なときにだけこの環境変数を読みます。temperature が 0 以下なら draft は argmax のままで、この設定は参照されません。

適用先は `STRATA_BUILD_SPLIT` で別途有効化する opt-in split engine です。Strata の通常 engine 全般を制御する設定ではありません。CMake の設定は既定 OFF で、split engine は Linux の CUDA/HIP 向けに構成されています（`CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-5`）。

## 値と判定

`env_int("FNX_DRAFT_SAMPLE", 1)` が環境値全体を符号付き base-10 `long long` に変換し、その結果が 0 かどうかで判定します。未設定の既定値は `1` です。0 以外の整数（負数も含む）は有効、0 は無効です。値の範囲制限や clamp はありません。

| 値 | 結果 |
| --- | --- |
| 未設定 | `1` として扱い、sampling draft を許可 |
| `0`, `+0`, `-0` | 無効 |
| 0 以外の整数（例: `1`, `-1`, `12`） | 有効 |
| 空文字、前後の空白、整数以外の文字、範囲外の整数 | 変換エラー |

変換は `strtoll` を使いますが、先頭文字が符号または数字であること、文字列末尾まで数字列として消費されること、overflow/underflow でないことも検査します。そのため ` 1`, `1 `, `1x`, 小数、空文字は受理されません。無効な文字列は `FNX_DRAFT_SAMPLE: '<値>' is not a whole number` という例外になります（`src/split/src/env.hpp:15-21,33-40`）。

## 有効になる条件

- `Session::generate()` では、まず sampling 設定の検査後に `sample = (temperature > 0)` を計算します。`sample` が false のとき C++ の短絡評価で `env_int()` 自体を呼ばないため、greedy 生成では値を読まず、誤った値でもこの経路からは変換エラーになりません（`src/split/src/session.cpp:397-410`）。
- `sample` が true で、かつ環境値が 0 以外なら draft 候補を sampling します。環境値が 0 なら draft head の argmax を使います（`src/split/src/session.cpp:439-449`）。
- batch decoder は `BatchDecoder` の構築時に無条件で値を読み、decoder インスタンスの `samp_drafts_` に保存します。実際の batch lane では、さらにその lane の `temperature > 0` が必要です（`src/split/src/batch.cpp:64-76,104-116`）。したがって batch decoder を作る経路では、greedy lane だけでも不正値は構築時の例外になります。
- CLI 引数による `FNX_DRAFT_SAMPLE` の上書きは見つかりません。CLI 等から渡された sampling 設定のうち、コード上この環境変数との併用条件になっているのは temperature です。

## 実行時の詳細

Session 経路では `Session::generate()` の呼び出しごとに値を評価し、結果を関数内ローカル変数に持ちます。プロセス全体の static cache ではありません。sampling が有効な場合、draft 呼び出しに候補出力を要求し (`Engine::draft(..., samp_drafts)`)、候補一覧から同じ `Sampling` の設定で分布を作って抽選します。無効の場合は候補出力を要求せず、draft head の argmax が draft token になります（`src/split/src/session.cpp:439-449`, `src/split/src/engine_common.cu:1371-1379`）。

sampled output の検証では、各 draft に対応する分布 `q` を用いて受理確率を計算し、不受理時は target 分布から draft 分布を差し引いた分布で補います。固定 draft の場合は `q` をその token に質量 1 の分布として扱います。このため、この変数は draft の選び方を変えますが、最終 token を draft head の分布から単純に出力する設定ではありません（`src/split/src/session.cpp:481-522`）。

batch 経路も同様に、sampling lane で `make_dist()` と lane RNG による抽選を行います。ここで読み取った値は `BatchDecoder` オブジェクトの寿命中保持されます（`src/split/src/batch.cpp:64-76,104-116,373-394`）。

不正値は共通 helper が `std::runtime_error` を投げます。standalone `fnx_run` の main は例外を stderr に `fnx_run: <例外内容>` と出し、終了コード 1 を返します（`src/split/tools/fnx_run.cpp:44-53`）。別の呼び出し元では、その呼び出し元の例外処理が結果を決めます。

## 根拠

- 候補一覧には `FNX_DRAFT_SAMPLE` が載っています（strata-envvars `docs/envvars/000_envvers.md:534`）。Strata 本番ソースの完全一致参照は `src/split/src/session.cpp:406-410`, `src/split/src/batch.cpp:76`, `src/split/src/batch.hpp:62`。header の記載は注釈で、読み取り箇所は `session.cpp` と `batch.cpp` の2箇所です。
- 整数 parse と例外文言: `src/split/src/env.hpp:15-21,33-40`。
- sampling 条件、draft head 呼び出し、候補からの抽選: `src/split/src/session.cpp:397-410,439-449`。
- verify 時の sampled/fixed draft 処理: `src/split/src/session.cpp:481-522`。
- batch decoder の読み取り時期と lane ごとの sampling 条件: `src/split/src/batch.cpp:64-76,104-116,373-394`。
- split engine の opt-in build 条件: `CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-5`。
- `docs/DETAILS.md` と他の設計文書に、この環境変数固有の追加条件や測定結果は見つかりませんでした。
