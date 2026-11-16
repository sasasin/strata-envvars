# `STRATA_PF_HASH_FILE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の batched prefill で、GDN (gated delta network) の中間バッファと recurrent state の行ごとのハッシュを指定ファイルへ出す診断用スイッチです。CUDA/HIP/Metal の同名実装は見つからず、SYCL の `strata_prefill` に含まれる `sycl/src/prefill/prefill.cpp` でのみ読み取ります (`sycl/CMakeLists.txt:271-275`, `sycl/src/prefill/prefill.cpp:170-175`)。

通常のモデル計算を別の演算へ切り替える値ではありません。対象 GDN 層の各段階で compute queue を待ち、device buffer を host へコピーしてハッシュを出力します。したがって診断 I/O と同期が加わりますが、ここでコピーしたデータをモデル計算へ書き戻す処理はありません (`sycl/src/prefill/prefill.cpp:3284-3321`)。

## 値と判定

`pf_hash_file()` は `std::getenv` で取得した文字列を、最初の呼び出し時に関数内 `static` の `FILE*` へ保存します。値を boolean や数値として parse せず、空でない文字列をそのまま `std::fopen(p, "w")` に渡します (`sycl/src/prefill/prefill.cpp:170-175`)。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL prefill の GDN 分岐 | `nullptr` を保存し、ハッシュ出力なし | 空文字でない値。例: `/tmp/pf-hash.txt` はその文字列を出力先として開こうとする。`1`、`true`、`false`、`0anything` も flag 値ではなく、それぞれの文字列をパスとして渡す | 空文字は `nullptr` となり出力なし。空白だけの値は空ではないためパスとして渡される |

文字列全体の検証、trim、大文字小文字変換、数値変換はありません。ファイルを開けず `fopen` が null を返した場合も、その null が保存されて出力は無効のままです (`sycl/src/prefill/prefill.cpp:171-175,3288-3298`)。

## 有効になる条件

- `sycl/src/prefill/prefill.cpp` を含む SYCL backend の実行経路であること。このソースは SYCL の `strata_prefill` に追加されています (`sycl/CMakeLists.txt:271-275`)。
- prefill の chunk 内で、`half == 0` かつ `core::is_qsa_layer(g, l)` が false の GDN 分岐へ入ること。GDN 層がないモデル・実行経路では helper が呼ばれず、環境値も読み取られません (`sycl/src/prefill/prefill.cpp:2601-2604,3276-3289`)。
- 実際に行ハッシュを書き出すには、さらに `gdn_index == 0` であること。`gdn_index` は各 chunk で `LB` より前の GDN 層数から始まるため、先行レイヤーを含む full-model prefill の先頭 GDN 層では true になります。先行層を除いた layer slice では ordinal 0 でない場合があり、その場合はファイルを開いてもハッシュ行は書きません (`sycl/src/prefill/prefill.cpp:2482,2789-2790,3284-3298`)。
- Strata 側に CLI 引数・設定ファイルによる別の値や優先順位は見つかりません。値の取得元はこの環境変数です (`sycl/src/prefill/prefill.cpp:170-175`)。

## 実行時の詳細

prefill は `c0` を chunk 長ずつ進めます。各 chunk のレイヤー走査で GDN 分岐に入ると `pf_hash_file()` が評価されます。関数内 static の初期化はプロセス内で一度だけなので、最初の GDN 分岐で unset/空文字だった場合やファイルを開けなかった場合、後から環境値を変えても反映されません。開けた場合も、以降の呼び出しは同じ `FILE*` を使います (`sycl/src/prefill/prefill.cpp:170-175,2601-2604,2789-2790,3284-3289`)。

`gdn_index == 0` の chunk では、`pfh` が各段階で compute queue を待ち、buffer 全体を host vector へ memcpy して完了を待ちます。その後、各行について `chunk stage row hash` 形式の行を `fprintf` し、段階ごとに `fflush` します。対象 stage は `mixed`, `qkv`, `z`, `ab`, `gate`, `beta`, `hbuf`, `y`, `state_rec` です。`state_rec` は recurrent state の `HV` 行を対象にします。chunk 番号は static 変数 `pfh_chunk` が最初に 0 となり、出力対象 chunk ごとに増加します (`sycl/src/prefill/prefill.cpp:177-181,3287-3321`)。

ファイルを開けなかった場合、`pfh_on` は false となり、`pfh` は何もせず戻ります。`fopen`、`fprintf`、`fflush` の失敗を報告する Strata 側のログや error 分岐はありません。ハッシュ出力は prefill の戻り値や生成結果を直接書き換えません。`Prefill::run` は `run_impl` の成功・失敗を返し、呼び出し元は prefill 自体が失敗した場合に `strata generate: <error>` を stderr に出して終了コード 1 を返しますが、これはこの変数固有のファイルエラー処理ではありません (`sycl/src/prefill/prefill.cpp:3288-3321,5335-5348`; `sycl/src/program/generate.cpp:12981-12985`)。

## ログと測定値

この変数が stdout/stderr に出すログはありません。指定ファイルには各行を `"%lld %s %lld %016llx\n"` の形式で書きます。ハッシュはコード上、各 byte に対して `h = (h ^ byte) * 1099511628211` を反復し、初期値 `1469598103934665603` を使います。測定値は該当資料にありません (`sycl/src/prefill/prefill.cpp:177-181,3290-3298`)。

## 根拠

- 値の取得・空文字判定・file open・static cache: `sycl/src/prefill/prefill.cpp:170-175`
- SYCL backend への組み込み: `sycl/CMakeLists.txt:271-275`
- chunk ごとの GDN index 初期化と GDN 条件: `sycl/src/prefill/prefill.cpp:2601-2604,2789-2790,3276-3289`
- queue wait、host copy、stage と state の出力: `sycl/src/prefill/prefill.cpp:3290-3321`
- prefill 失敗の呼び出し元での stderr と終了: `sycl/src/prefill/prefill.cpp:5335-5348`; `sycl/src/program/generate.cpp:12981-12985`
