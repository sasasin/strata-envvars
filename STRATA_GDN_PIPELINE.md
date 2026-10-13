# `STRATA_GDN_PIPELINE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。開始時の作業ツリーは `main...origin/main` で、Strata リポジトリには本調査と無関係な未追跡のベンチマーク結果ディレクトリがあった。調査対象は Strata 所有ソース。外部ライブラリの環境変数動作は対象外。

## 役割

GDN（gated delta network）の prompt prefill における再帰計算で、token ごとの入力を先読みする software-pipelined 列分割カーネルを使うか、先読みしない列分割カーネルを使うかを切り替える。これはカーネル実装を選ぶ設定で、`STRATA_GDN_PIPELINE` 自体は GDN 計算値を変換しない。

通常の GDN layer の prefill は射影・gate・畳み込みの後に `gdn_recurrence()` を呼ぶ。この関数は `gdn_recurrence_variant()` に処理を渡し、後者の条件を通った場合に環境変数を読み、再帰カーネルを選ぶ。CUDA/HIP の通常経路では、ON は先読み版 `gdn_rec_cols_pipe_kernel`、OFF は `gdn_rec_cols_kernel` を実行する。CUDA の一部デバイスでは別の key-head カーネルが選ばれることもある（後述）。

## 値と判定

`std::getenv()` の値を `std::atoi()` に渡し、未設定なら ON、設定済みなら変換結果が 0 以外のとき ON とする。文字列全体の数値検査はしない。

| 環境値 | 判定 |
|---|---|
| unset | ON |
| `0`、`00`, `0tail`、空文字、数値に変換できない文字列 | OFF（`atoi` が 0） |
| `1`、`-1`、`2tail`、先頭空白の後に非ゼロ整数がある文字列 | ON（`atoi` が非 0） |

したがって `true` / `false` はどちらも `atoi` が 0 を返すため OFF。先頭の空白や符号は `atoi` の通常の変換に従い、数値の後ろの文字列は判定に影響しない。オーバーフロー時の `atoi` の結果には依存できないため、値として使うべきではない。

判定値は関数内の `static const bool` に一度保存される。実際にこの分岐へ初めて到達した後、プロセス内で環境を書き換えても再評価されない。読み取りは未設定を ON と扱う。

## 有効になる条件

環境変数を読んで分岐するのは、`STRATA_GDN_REC_HEADS` が未設定で、`T > 0` かつ `variant != 2` の場合だけ。`STRATA_GDN_REC_HEADS` は値の内容でなく設定有無で判定され、空文字を含め設定されていると一ブロック/一 head の再帰カーネルへ進み、この設定は評価されない。`T <= 0` と `variant == 2` も通常再帰カーネルへ進み、この設定を評価しない。

AMD/HIP build では `STRATA_GDN_HEAD` により `variant == 1` に選ばれると、quad recurrence の分岐が `STRATA_GDN_PIPELINE` の分岐より先に return する。gfx1151 と gfx12 では起動時の architecture defaults が、ユーザーが未設定なら `STRATA_GDN_HEAD=1` を環境に設定する。そのため既定設定ではこの設定は評価されず、`STRATA_GDN_HEAD=0` を明示するか、architecture defaults 全体を無効にして `variant == 0` にするなど、通常再帰経路に入った場合に使われる。`STRATA_GDN_REC_HEADS` が設定されている場合は `variant == 0` でも一ブロック/一 head 経路へ進むため、やはり評価されない。CUDA build ではこの AMD 専用 `variant == 1` 分岐はない。

追加の経路差:

- CUDA では `STRATA_GDN_CHUNKED` が `atoi != 0` で、`T >= kGdnChunkedMin` かつ chunked scratch/launch が成功すると、chunked recurrence が選択され、pipeline の値にかかわらず後続の pipeline 分岐を通らない。chunked が不適用または失敗した場合は下記の選択へ進む。
- CUDA では pipeline が ON のときだけ `gdn_keyhead_ok()` を検査する。この helper は `STRATA_GDN_KEYHEAD=0` で明示的に止められておらず、GPU が compute capability 8.0 以上で occupancy 条件を満たすと、`gdn_rec_kh_kernel` が選ばれる。その条件を満たさない場合は software-pipelined 列分割版へ進む。pipeline が OFF の場合は key-head kernel を検査せず、通常の列分割版を使う。
- HIP の通常再帰経路では CUDA 専用の chunked recurrence と key-head 選択がコンパイル対象外で、pipeline の ON/OFF がそれぞれ pipe/plain の列分割版を選ぶ。
- 通常の GDN prefill 呼び出し元はモデルの layer 種別で GDN を処理し、計算対象の token 数 `T` を再帰関数へ渡す。これは decode loop 全般の設定ではない。
- AMD/HIP の `strata generate` は engine が環境スイッチを読む前に `apply_arch_defaults()` を呼ぶ。gfx1151 と gfx12 の defaults は `STRATA_GDN_HEAD=1` を含み、ユーザーが既に設定した値は保持する。`STRATA_GFX1151_DEFAULTS=0` または `STRATA_GFX12_DEFAULTS=0` は各 architecture の defaults 適用を止める。

## 実行時の詳細

ON 時の `gdn_rec_cols_pipe_kernel` は token `t` の計算中に `t+1` の q/k/v/gate/beta を register に先読みしてから次の反復に使う。OFF 時の `gdn_rec_cols_kernel` は各反復でその token の q/k を共有メモリへ読み、同じ列分割の再帰と出力を処理する。両カーネルのソースコメントは、同じ演算順・同じ bit 結果と説明している。これは実装コメントにある性質であり、本調査で GPU を実行して独立検証した結果ではない。

設定によるログ出力、警告、終了動作は確認できない。`docs/DETAILS.md` は `STRATA_GDN_CHUNKED` の条件付き測定を記載しているが、`STRATA_GDN_PIPELINE` の値や性能測定は記載していない。そのため pipeline の速度向上や性能差はここでは主張しない。

SYCL にも `sycl/src/prefill/kernels.dp.cpp` に対応する環境読み取りとカーネル分岐がある。しかし同ファイルは CUDA ソースの DPCT 移行コードであり、調査手順の「生成済みコードを根拠にしない」に従って、上記の挙動説明の根拠には使っていない。SYCL でのビルド成果物に対する独立確認は行っていない。

## 根拠

- `src/prefill/kernels.cu:1974-1994` — serial / `T` / variant の早期分岐、`STRATA_GDN_PIPELINE` の `getenv`・`atoi` 判定、CUDA chunked/key-head/pipeline/plain カーネルの選択と最終チェック。
- `src/prefill/kernels.cu:495-553` — 先読み版の処理と、同じ演算順に関する実装コメント。
- `src/prefill/kernels.cu:696-712` — CUDA の key-head カーネル有効条件と `STRATA_GDN_KEYHEAD` の判定。
- `src/prefill/kernels.cu:1931-1973,1996-2003` — HIP の variant 分岐、`STRATA_GDN_HEAD` による dispatch、recurrence 呼び出し。
- `src/core/arch_defaults.cpp:12-34,61-81` と `src/program/generate.cpp:2152-2158` — gfx1151/gfx12 で `STRATA_GDN_HEAD=1` を既定設定し、ユーザー値を保つ起動時処理。
- `src/prefill/prefill.cpp:2603-2626` — GDN prefill の処理から `gdn_recurrence()` を呼ぶ位置。
- `CMakeLists.txt:586-589` — CUDA/HIP build の `strata_prefill` に `src/prefill/kernels.cu` を含める。
- `docs/DETAILS.md:1668-1679` — GDN chunked の性能記載。pipeline 自体の記載・測定根拠ではない。
