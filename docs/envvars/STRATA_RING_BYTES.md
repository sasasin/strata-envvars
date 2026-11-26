# `STRATA_RING_BYTES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prefill のリングをバイト予算として扱う方式と、それに合わせた自動 chunk／expert-cache loan の選択を切り替える。既定（unset）では有効で、`0` で旧方式に戻す。CUDA/HIP 系の `engine/src/prefill/prefill.cpp` と SYCL の `engine/sycl/src/prefill/prefill.cpp` に同じ読み取り関数があり、CLI・サーバーどちらから呼ばれても engine 内で作用する。SYCL では追加で特定の 8192-token window workspace 再利用の条件にも使われる。`engine/src/prefill/prefill.cpp:833-835, 3912`、`engine/sycl/src/prefill/prefill.cpp:281-284, 2523, 1323-1325`。

## 値と判定

両実装とも `std::getenv` の戻り値を関数内 `static const bool` に保存し、値全体を parse せず先頭 1 byte だけを見る。unset は有効、設定値の先頭が文字 `0` なら無効、それ以外は有効。したがって空文字は有効、`0`・`0anything`・`00` は無効、`1`・`true`・`false`・`anything`・先頭空白の ` 0` はいずれも有効。数値妥当性、大文字小文字、末尾文字は検査しない。`engine/src/prefill/prefill.cpp:833-835`、`engine/sycl/src/prefill/prefill.cpp:281-284`。

| 実装 | unset | 有効になる設定値 | 無効になる設定値 |
|---|---|---|---|
| CUDA/HIP 系共通 engine | 有効 | 空文字、`1`、`true`、`false`、`anything`、` 0` | `0`、`0anything`、`00` |
| SYCL engine | 有効 | 空文字、`1`、`true`、`false`、`anything`、` 0` | `0`、`0anything`、`00` |

## 有効になる条件

- バイト予算を使った chunk／loan 選択は `--prefill auto` の自動選択経路で使われる。明示的な `--prefill N` は自動選択の旧 chunk リスト／バイト予算スキャンを通らない。CUDA/HIP 系では `engine/src/program/generate.cpp:11346-11351, 11388-11409`、SYCL では `engine/sycl/src/program/generate.cpp:6713-6718, 7311-7332`。
- 自動経路では、CUDA/HIP 系は expert cache から借りる余地をバイトで計算し、収まる ring と chunk を探索する。SYCL も同様に room を計算する。値が有効でも、chunk が収まらない場合は旧方式の候補／fallback が使われる。`engine/src/program/generate.cpp:11361-11409`、`engine/sycl/src/program/generate.cpp:7317-7332`。
- `STRATA_PREFILL_RING` が設定されると ring slot 数の選択ではその値が優先され、bytes 方式の計算した予算が ring 数を置き換えない。なお、変数が有効な場合の自動 chunk 探索自体は残り、探索時にも `STRATA_PREFILL_RING` を考慮する。`engine/src/prefill/prefill.cpp:843-879`、`engine/sycl/src/prefill/prefill.cpp:291-323`、`engine/src/program/generate.cpp:11388-11397`、`engine/sycl/src/program/generate.cpp:7320-7327`。
- SYCL の `pair_window` は bytes 方式が有効で、window layout、`T == 8192`、gate workspace 共有が成立し、CVEC がロードされていない場合だけ有効になる。`STRATA_RING_BYTES=0` ではこの追加条件を満たさない。`engine/sycl/src/prefill/prefill.cpp:1306-1327, 1648-1652`。
- 判定関数に OS・backend・build macro の条件分岐はない。ただし、そのソース実装を含む実行経路に限られる。CUDA/HIP 系と SYCL のコードが別に存在する。`engine/src/prefill/prefill.cpp:833-835`、`engine/sycl/src/prefill/prefill.cpp:281-284`。

## 実行時の詳細

初回に `ring_bytes_on()`／`ring_bytes_enabled()` が呼ばれた時点のプロセス環境を読み、関数内 static に保存する。その後プロセス内で環境値を変更しても判定は更新されない。共通 helper `Prefill::ring_bytes_enabled()` はこの保存値を返す。`engine/src/prefill/prefill.cpp:833-835, 3912`、`engine/sycl/src/prefill/prefill.cpp:281-284, 2523`。

有効時、`ring_slots()` は自動設定された `g_ring_budget` があり、chunk が `g_ring_small_max` を超えると、その予算を既定 slot 数より優先する。slot 数は blob サイズから換算され、上限 `ring_cap()` に clamp される。ring override、`STRATA_PREFILL_RING`、pinned share、fused ring などにより最終 slot 数は変わる。無効時はこの `g_ring_budget` 経路を使わず、従来の pinned ring と旧自動 chunk 候補リストを使う。`engine/src/prefill/prefill.cpp:808-841, 843-879`、`engine/sycl/src/prefill/prefill.cpp:264-289, 291-323`、`engine/src/program/generate.cpp:11335-11409`、`engine/sycl/src/program/generate.cpp:6701-6718`。

値は ring 選択だけでなく、`Prefill::bytes_needed_impl()` の scratch buffer 見積もりにも使われる。有効時は `gr_unfused()` に応じた追加領域を数え、無効時は旧式の領域サイズを数える。SYCL では `reuse_hc` が成立する場合に共有領域の分を省く。したがって見積もりと、それを使う fit／loan 判断も変わる。`engine/src/prefill/prefill.cpp:3718-3742`、`engine/sycl/src/prefill/prefill.cpp:2423-2462`。

## ログと測定値

この変数専用のログ、警告、終了コードはない。選ばれた chunk が通常の prefill 情報として表示される経路では `strata prefill: ... tokens in ...-token chunks ...` が出る。バッファ割当てが失敗した場合は `prefill: device buffers for a chunk of ... tokens do not fit (...)` がエラー文字列となり、呼び出し元に返る。`engine/src/prefill/prefill.cpp:3694-3699, 2738-2746, 2949-2958`。

`docs/DETAILS.md:1766-1769` は RTX 5070 の 32K prompt、`STRATA_RING_BYTES=0` との 2–3 回の交互測定（engine 0.1.39b）として量子化別の差と teacher-forced 指標を記載している。これは同資料に記載された測定結果であり、この調査で再測定した値ではない。`docs/DETAILS.md:1766-1769`。

## 根拠

- 判定と cache: `engine/src/prefill/prefill.cpp:833-835, 3912`; `engine/sycl/src/prefill/prefill.cpp:281-284, 2523`
- ring slot の優先順位と clamp: `engine/src/prefill/prefill.cpp:814-841, 843-879`; `engine/sycl/src/prefill/prefill.cpp:267-289, 291-323`
- CUDA/HIP 自動選択: `engine/src/program/generate.cpp:11335-11409`
- SYCL 自動選択と pair window: `engine/sycl/src/program/generate.cpp:6713-6718, 7311-7332`; `engine/sycl/src/prefill/prefill.cpp:1323-1327, 1648-1652`
- 見積もり差と割当て失敗: `engine/src/prefill/prefill.cpp:3718-3742, 2738-2746`; `engine/sycl/src/prefill/prefill.cpp:2423-2462`
- 資料上の測定値: `docs/DETAILS.md:1766-1769`
