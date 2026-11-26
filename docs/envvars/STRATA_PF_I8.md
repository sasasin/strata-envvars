# `STRATA_PF_I8`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL の prompt 処理で使う fused int8 expert products の選択値です。`STRATA_PREFILL_MMQ` が未設定または空文字のとき、この変数を alias として読みます。対象経路では、条件を満たす expert group の gate/up・SwiGLU・down を int8 DPAS カーネルで処理し、使わない場合は既存の FP16 dequantize + oneMKL 経路へ進みます。alias の読み取りとモード判定は `engine/sycl/src/prefill/prefill.cpp:333-350`、処理切替は同 `:4773-4780` と `:4862-4932` です。

CUDA/HIP や Strata の他のコードでこの名前を読む箇所は、候補名の全参照検索では見つかりませんでした。従って、この名前単独では SYCL 以外の prompt 経路を制御しません。

## 値と判定

`i8_env()` はまず `std::getenv("STRATA_PREFILL_MMQ")` を読み、その値が未設定または空なら `STRATA_PF_I8` を読みます。両方が未設定または空なら unset として扱います。非空の primary 値は alias に優先します。読み取り結果は `i8_env()` / `i8_mode()` の呼び出しごとに取得し、alias 自体を保存する static cache はありません（`engine/sycl/src/prefill/prefill.cpp:333-350`）。

| `STRATA_PREFILL_MMQ` | `STRATA_PF_I8` | 判定 |
|---|---|---|
| 非空 | 任意 | primary 値だけで判定。alias は無視 |
| 未設定または空 | 未設定または空 | unset。Battlemage と kernels が使える場合だけ auto、それ以外は FP16 |
| 未設定または空 | 非空 | 下記の文字列判定 |

非空値は文字列全体の比較や `atoi` ではなく、先頭だけを判定します。先頭が `a` または `A` なら後続文字列に関係なく auto（モード 2）。それ以外は先頭から連続する ASCII 数字を `long` に累積し、値が 1 以上なら int8 強制（モード 1）、0 なら FP16（モード 0）です。累積値が 1,000,000 以上になると追加の数字は読みません。従って `1`, `1junk`, `0002` は int8、`0`, `0anything`, `000` は FP16、`auto` / `AUTO` / `aJunk` は auto です。`true`、`false`、先頭空白付きの数字、`-1`、英字で始まる値（`auto` の a/A を除く）は数字列が 0 桁または 0 のため FP16 になります。大文字小文字は auto の先頭 `a` だけを区別せず、空白除去や全体 parse はしません（`engine/sycl/include/strata/prefill/esimd_moe.hpp:39-50`）。

## 有効になる条件

- SYCL port の prompt expert 処理でのみ参照されます。Strata の shell launcher は `STRATA_*` 環境をコンテナへ渡しますが、これは転送処理であり別 backend の実装を意味しません（`engine/sycl/serve/strata-sycl.sh:33-43`）。
- 設定が unset/空のときの自動選択は、実行デバイスが architecture ID で Battlemage と判定され、かつ当該ビルドで kernel が利用可能な場合に auto です。それ以外は FP16 です。`battlemage()` と `available()` がこの判定に使われます（`engine/sycl/src/prefill/prefill.cpp:340-350`; `engine/sycl/src/prefill/esimd_moe.dp.cpp:824-827,840-858`）。
- 明示値が int8 または auto でも、実際の `i8on` には ESIMD kernel の利用可能性が必要です。AOT の対象外、または `STRATA_SYCL_I8_ESIMD=OFF` の build は stub となり `available()` は false です（`engine/sycl/CMakeLists.txt:78-96`; `engine/sycl/src/prefill/esimd_moe.dp.cpp:41-61`）。さらに `STRATA_I8_FORCE` の先頭が `0` なら `available()` を false にします。この判定は device ごとに static map へ cache されます（同 `esimd_moe.dp.cpp:840-858`）。
- native expert layout であり、Hadamard fold が gate/up と down のどちらにもなく、gate/up 型が IQ3_S (21) / IQ3_XXS (18) / IQ2_S (22)、down 型が IQ4_NL (20) / Q2_0 (42)、`n_ff == 640`、`n_embd == 2560` である必要があります。別形式・寸法は int8 の対象になりません（`engine/sycl/src/prefill/prefill.cpp:4775-4780`）。
- `STRATA_PF_XMX=2` で当該 layer が `xmx2_fmt()` の対象になると `xmx2_only` が立ち、fused int8 DPAS は使われません。これは XMX grouped 経路の優先条件です（`engine/sycl/src/prefill/prefill.cpp:4754-4772,4775-4781`）。
- `STRATA_PREFILL_MMQ` が有効でその layer が MMQ plan の対象なら `use_mmq` が立ち、fused int8 条件の `!use_mmq` によりこの経路は使われません。MMQ plan は `STRATA_PREFILL_MMQ` だけを直接読み、`STRATA_PF_I8` を見ません。primary の `atoi` が 0 以外なら MMQ を有効にする一方、primary が空で alias を int8 指定しても、MMQ が built で対象 layer を持てば MMQ が優先されます（`engine/sycl/src/prefill/prefill.cpp:1255-1275,3945-3946,4775-4780`）。
- `STRATA_PREFILL_MMQ=0` は alias より優先され、MMQ plan を無効にし、同時に int8 モードも 0 にします。従って alias の int8 指定を打ち消して FP16 を選びます（`engine/sycl/src/prefill/prefill.cpp:333-345,1255-1264`）。
- auto は対象 group ごとに実行時の行数と、GPU / driver / format / shape ごとの crossover を使います。format ごとに queue 内で較正結果を保持し、ディスク上の `i8-crossover.txt` に一致キーがあれば再利用します。較正失敗時は 64 rows/expert 未満で int8 を使う扱いです（`engine/sycl/src/prefill/prefill.cpp:948-979,1005-1018,1099-1129,4867-4878`）。

## 実行時の詳細

alias は prompt の `Prefill::init` の通知判定、stage slot 数の見積り、各 expert layer のモード選択で helper 経由に再評価されます。環境変数名の値を process 起動時に一度だけ cache する処理はありません。一方、int8 kernel launch に例外が出ると `g_i8_failed` が process 内で true に固定され、以後 `i8_mode()` はモード 0 を返します（`engine/sycl/src/prefill/prefill.cpp:333-350,1415-1419,4775-4780`; 同 `:338-344,4917-4921`）。

int8 が選ばれた layer でも、group の実行時に workspace 確保または対象 format の kernel 呼び出しが成立しなければ、その group は FP16 chain に戻ります。auto は較正 crossover より平均 rows/expert が小さい group を int8 にし、それ以上を FP16 にします（`engine/sycl/src/prefill/prefill.cpp:4862-4872,4887-4915,4931-4932`）。この変数が切り替えるのは prompt expert の積の計算経路です。生成結果が同一になることはこの変数の実装からは保証できません。

## ログと測定値

`i8_mode()` が非ゼロなら初回の `Prefill::init` で stderr に `strata: int8 prompt experts are on (%s); STRATA_PREFILL_MMQ=0 turns them off` を一度出します。alias 指定時も文面は alias 名ではなく `STRATA_PREFILL_MMQ set` と表示されます。非zero モードでもデバイスや形式条件を満たさない場合、後続ログの layer ごとの `int8 path no` で確認できます（`engine/sycl/src/prefill/prefill.cpp:1416-1419,4782-4787`）。

int8 実行を試みたが workspace または kernel が format を扱えない場合は `strata: the int8 expert products could not run (layer ..., no workspace or a format they do not handle): the FP16 chain is used`、launch 例外時は `strata: the int8 expert kernels failed to launch (...): the FP16 expert chain is used from here` を stderr に出します。auto の較正成功時は実測値と crossover、cache 使用時は cache の crossover を stderr に出します。較正失敗時は理由と 64 rows/expert の fallback を stderr に出します（同 `prefill.cpp:1015-1018,1099-1101,1126-1128,4910-4920`）。

## 根拠

- `engine/sycl/src/prefill/prefill.cpp:333-350` — primary / alias の選択、値の読み取り、既定モード、失敗時のモード。
- `engine/sycl/include/strata/prefill/esimd_moe.hpp:39-50` — 値の文字列判定規則。
- `engine/sycl/src/prefill/prefill.cpp:1255-1275,3945-3946,4773-4787` — MMQ との競合、実際の適用条件、layer ごとの診断。
- `engine/sycl/src/prefill/prefill.cpp:4862-4932` — auto の group 選択、int8 実行と FP16 fallback。
- `engine/sycl/CMakeLists.txt:78-96`; `engine/sycl/src/prefill/esimd_moe.dp.cpp:41-61,824-858` — build stub、device capability、`STRATA_I8_FORCE`。
- `engine/sycl/src/prefill/prefill.cpp:948-1129` — auto crossover の cache・較正・ログ。
- `engine/sycl/serve/strata-sycl.sh:33-43` — SYCL launcher の環境変数転送。
