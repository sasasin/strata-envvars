# `STRATA_Q6_PACKED`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソース。外部ライブラリの動作と測定記録は根拠にしていない。

## 役割

Q6_K の出力 head（通常の `output.weight` と、条件を満たす MTP draft head）をロード時に別の平面配置へコピーします。登録された head に対する native MMVQ の呼び出しは、そのコピーを読む packed kernel に切り替わります。量子化値を変換する機能ではなく、各ブロックの `ql`、`qh`、`scales`、`d` のバイトを分けて並べた追加コピーです。

対象はこの native head 経路です。ソース上では Q6_K の全行列を一律にパックせず、`NativeHead::load()` と、MTP が head から token subset を作る経路だけが登録を試みます。

## 値と判定

カーネル側の `native_q6_k_packed_enabled()` は `getenv("STRATA_Q6_PACKED")` の結果が文字列全体でちょうど `1` の場合だけ有効とします。先頭文字だけの比較ではなく、数値変換もしません。

| 環境変数の状態 | 判定 |
|---|---|
| 未設定 | 通常は無効。後述の gfx1151 HIP 既定値が適用された場合は `1` が設定される |
| 空文字 | 無効。設定済みなので gfx1151 の自動既定値も抑止する |
| `1` | 有効 |
| `01`, `10`, `1x`, `true`, `0` など | 無効 |

判定結果は関数内の `static const bool` に保存され、プロセス内の初回呼び出し時に一度だけ読み取られます。その後に環境を書き換えても再判定しません。gfx1151 の既定値設定は、生成処理が engine の設定を読む前に行われます。

## 有効になる条件

環境変数の判定が true でも、パック対象の Q6_K 行列が次を満たす必要があります。

- 重みポインターが null でない。
- `n_in > 0` かつ `n_in` が 256 の倍数。
- `n_in / 256 >= WARPS * WARP / 32`。
- `n_out >= 2048`。

形状が対象外、コピーや割り当てに失敗、または registry に対象ポインターがなければ、パック版は使われず通常の Q6_K MMVQ に進みます。multi-column 呼び出しでは `g_multi_exact` が false の場合も packed dispatch が辞退します。登録済みでも、解除後は同じく通常経路です。

HIP の `STRATA_USE_HIP` build では、`generate` が gfx1151 と判定したときにアーキテクチャ既定値表が `STRATA_Q6_PACKED=1` を追加します。ただし、利用者が変数を何らかの値（空文字を含む）に設定済みなら、その値が優先されます。また `STRATA_GFX1151_DEFAULTS` の先頭文字が `0` なら既定値表全体が無効になり、この変数も自動設定されません。gfx1200/gfx1201 用の既定値表にはこの変数がなく、CUDA build ではこの gfx1151 既定値設定ブロック自体が実行されません。したがって、それらの環境で使うには明示的に `STRATA_Q6_PACKED=1` を設定します。

## 実行時の詳細

`NativeHead::load()` は GGUF の出力重みを device に読み込んで型を記録した後、型 ID が 14（Q6_K）で、環境判定が有効なら `native_q6_k_pack()` を呼びます。MTP の subset head も、subset 作成後の型が Q6_K であれば同じ登録を試みます。pack 関数の戻り値は呼び出し側で処理分岐に使わず、登録に失敗した場合も head のロード自体を失敗扱いにはしません。

pack 関数は GGUF 配置の device 重みを host に読み戻し、Q6_K block ごとの 128 byte `ql`、64 byte `qh`、16 byte `scales`、2 byte `d` を、それぞれ 256 byte 境界にそろえた平面へコピーします。その平面一式を別の device allocation に転送し、元の重みポインターをキーに registry へ登録します。追加 VRAM はほぼ元の重みサイズ分です（平面境界の padding を含みます）。成功時は stderr に `strata: STRATA_Q6_PACKED=1 packed the %s (%d x %d, +%.1f MiB)` を出します。対象外や失敗時にはこの成功ログは出ません。

`native_q6_k_mmvq()` の入口では registry を調べ、登録があり、shape が一致し、バイパス中でなく、column 条件を満たせば packed kernel を起動します。それ以外は従来の Q6_K kernel に進みます。実装コメントと API 宣言は packed 配置を同じ元バイトの再配置とし、出力が元 kernel と bitwise equal と説明しています。`STRATA_Q6P_SELFTEST` はロード時の比較・タイミング診断を追加する別変数で、`STRATA_Q6_PACKED` の有効値判定ではありません。

NativeHead の破棄時、および所有する MTP subset head の破棄時に registry 登録を解除し、packed allocation を解放します。共有 MTP head の所有権は共有元に残ります。

## 文書と測定値

`docs/STRIX_HALO.md` はこの変数を Q6_K packed decode layout の一つとして列挙していますが、この調査時点で参照した `docs/DETAILS.md` には `STRATA_Q6_PACKED` の個別説明や性能測定値を確認できませんでした。したがって、速度向上率は記載しません。

## 根拠

- 読み取り、完全一致判定、形状条件、平面コピー、registry、成功ログ、dispatch、通常 kernel への fallback: `src/kernels/cuda/native_mmvq.cu:1810-1826,1898-1942,1980-2018,2345-2369`。
- native head のロード時登録と破棄時解除: `src/core/native_head.cpp:15-18,61-69`。
- MTP subset head の登録・MMVQ 呼び出し・解放: `src/core/mtp.cpp:130-157,655-680,995-998`。
- gfx1151 既定値、明示設定優先、gfx12 では Q6 packed 既定値なし: `src/core/arch_defaults.cpp:12-58,61-80`。
- 既定値適用の build 条件と engine の初回読み取りより前に適用する順序: `src/program/generate.cpp:2190-2196`; HIP build の定義: `cmake/hip_backend.cmake:85-90`。
- Strix Halo 文書の一覧: `docs/STRIX_HALO.md:95`。
