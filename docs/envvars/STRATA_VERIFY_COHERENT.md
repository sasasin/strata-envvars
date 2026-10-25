# `STRATA_VERIFY_COHERENT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数の意味は対象外。

## 役割

HIP verifier が host/device 間で共有する mapped host memory の割り当て方法を選びます。有効時は `hipHostMallocCoherent` を指定して、handshake words、window staging、verify trace など `mapped()` を通る領域を確保します。無効時は通常の `hipHostMallocMapped`（必要なら peer 用の portable flag も付加）を使います。

CUDA ビルドではこの変数を読みません。SYCL の `mapped()` はこの値で割り当て方法を変えません。

## 値と判定

`env_on()` は `getenv()` の結果が存在し、空文字でなく、先頭文字が `0` でない場合に true を返します。文字列全体の parse や数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0`、`0anything` | 無効 |
| `1`、`2`、`true`、`false`、空白から始まる文字列など | 有効（先頭文字が `0` 以外） |

大文字小文字や後続文字は判定に影響しません。値は `src/core/verify.cpp` の namespace-scope `const bool` 初期化時に一度読みます。そのため、プロセス起動後に環境を書き換えても再評価されません。

## 有効になる条件

- `src/core/verify.cpp` の HIP ビルド（`STRATA_USE_HIP`）でのみ、値が allocation の選択に使われます。CUDA では HIP 専用の `g_coherent` 自体が定義されず、この環境変数の参照もありません。
- 有効値でも、実際に verifier が mapped host memory を確保する経路に入ったときに適用されます。HIP の `mapped()` は `hipHostMallocCoherent` を加えて確保し、割り当て失敗時は false を返します。呼び出し元は mapped staging allocation failure などのエラーで初期化を失敗させます。通常割り当てへの自動 fallback はありません。
- `sycl/src/core/verify.cpp` にも同名の読み取りがありますが、そこでは `STRATA_USE_HIP` 条件下で `g_coherent` を宣言し、verify trace の診断行に `explicit` / `default` と表示するだけです。SYCL の `mapped()` は `window_host_uncached()` に応じて `host_malloc_polled()` または `sycl::malloc_host()` を使い、この変数を参照しません。

## 実行時の詳細

HIP の allocation 選択は `mapped()` に集約されています。Verifier の初期化時には token、position、commit、output、sequence/flag、plan などの mapped staging buffer をこの関数で確保します。追加の trace buffer、layer hand-off 用の語、batch commit staging も同じ関数を通ります。したがって、この変数が変更するのはこれら領域の host allocation flag です。計算内容や verify handshake のアルゴリズムを直接変更する分岐はありません。

`STRATA_VERIFY_TRACE` が有効で trace buffer の確保が行われる HIP 実行では、stderr に `strata verify trace (#649): on; coherent words explicit|default, ...` が出て、選ばれた allocation モードを確認できます。trace が有効でない場合、この変数だけを理由にログは出ません。

SYCL ファイルのコメントはこの設定を gfx1030 の verify timeout 調査における opt-in A/B 設定として説明しています。ただし、対象 HEAD のソースだけでは `hipHostMallocCoherent` が外部 runtime/driver 上でどう実現されるか、また timeout を改善するかは確認できません。`docs/AMD_HIP.md` の Linux timeout 節は別の host memory reclaim 仮説と環境変数を扱い、この設定の測定値や効果は記載していません。

## 根拠

- `src/core/verify.cpp:217-227` — HIP 向け設定コメント、値判定、HIP 条件付きの初期値。
- `src/core/verify.cpp:414-427` — HIP 有効時の `hipHostMallocCoherent` と無効時の通常 mapped allocation。
- `src/core/verify.cpp:747-765,858-865,3315-3321` — 通常 staging、hand-off/trace、batch commit の mapped allocation 呼び出し。
- `src/core/verify.cpp:869-877` — trace 有効時の HIP 診断ログ。
- `sycl/src/core/verify.cpp:90-101,230-243,621-635` — SYCL 側の読み取り条件、mapped allocation 実装、trace ログ。
- `docs/AMD_HIP.md:404-428` — HIP timeout の関連資料。`STRATA_VERIFY_COHERENT` の動作・測定は説明していない。
