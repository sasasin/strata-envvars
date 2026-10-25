# `STRATA_PREFILL_WARM`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有ソースと同 revision の文書。外部ライブラリ内部の環境変数動作は対象外。

## 役割

HIP backend の prefill が使う BF16 / FP16 GEMM ライブラリの初回ロードを、小さな GEMM を先に実行して済ませます。`generate` は GPU が識別できた場合、expert arena の読み込み前に専用スレッドを起動します。目的は初回 prompt にライブラリの初期ロード時間が乗るのを避けることです。CUDA と SYCL ではこの warm-up 処理本体はありません。

## 値と判定

値全体や数値としての妥当性は parse せず、先頭文字だけを比較します。

| 値 | 判定 |
|---|---|
| unset、空文字、先頭が `0` / `1` 以外 | 自動判定 |
| 先頭が `0`（例: `0`, `0foo`） | 無効。warm-up を行わない |
| 先頭が `1`（例: `1`, `10`, `1foo`） | 強制有効。複数 GPU の architecture が異なっても実行対象にする |

したがって `false` は無効化ではなく自動判定、`true` は強制有効ではなく自動判定です。環境変数は `warm_gemm_libraries()` の最初の呼び出しで `static` 値として評価され、その後同じプロセス内で環境を変更しても再評価されません。HIP の architecture 判定も別の `static` 値に保存されます。

## 有効になる条件

- `STRATA_USE_HIP` を定義したビルドでのみ GEMM warm-up が実装されています。HIP 以外では関数は `device` を使わず終了します。
- `generate` 起動時に `cudaGetDevice()` と `cudaGetDeviceProperties()` が成功して GPU が識別できた場合、現在の device を対象にバックグラウンドスレッドを開始します。識別に失敗するとこの起動時スレッドは作られません。
- HIP では、明示値が先頭 `0` なら無効、先頭 `1` なら architecture によらず有効です。その他の値は見えている GPU の architecture によって決まります。同じ architecture だけなら有効、異なる architecture が一つでもあれば無効です。architecture 名の `:` 以降の feature suffix は比較対象から除外されます。
- architecture の列挙は device 0 から最大 32 台までです。`cudaGetDeviceCount()` が失敗した場合はエラーを消費して architecture 条件を通過扱いにし、warm-up を許可します。個別 device の property 取得に失敗した device は一覧に追加されません。
- architecture 一覧が空なら自動判定は warm-up を許可します。対象 device index が 0–31 の範囲外なら、その device の warm-up は行いません。device ごとの mask は実処理を始める前に立つため、API 失敗時も含め、同じ device ではプロセス内で一度しか試行しません。

## 実行時の詳細

`warm_gemm_libraries(device)` はまず `STRATA_PREFILL_WARM` の先頭文字が `0` かを判定します。HIP では続いて全 GPU の architecture を調べ、異なる architecture があり自動判定で無効になったとき、stderr に `strata prefill: no hipBLAS warm-up: the cards are of more than one architecture (it slows prompts there, #3204); the first prompt loads the libraries (STRATA_PREFILL_WARM=1 asks for it)` を出します。

許可された device では mutex と device ごとの完了 mask で重複実行を避けます。専用 stream と scratch buffer を用意し、`T=64, N=64, K=320` のゼロ入力で BF16 と FP16 の GEMM を実行して stream を同期し、buffer と stream を解放します。GEMM 初期化まで成功した場合は stderr に `strata prefill: warmed the BF16 and FP16 GEMM libraries on GPU ... in ... ms (STRATA_PREFILL_WARM=0 skips)` と所要時間を出します。確保または GEMM 初期化に失敗した場合、成功ログは出ません。関数内で CUDA/HIP API のエラーを消費しますが、warm-up 失敗を示す専用エラー文は出しません。

起動時スレッドは `generate.cpp` の GPU 情報取得後、expert arena の読み込み箇所より前に開始され、終了時に join されます。さらに `Prefill::init()` からも現在の device に対して同じ関数が呼ばれます。起動スレッドが処理中なら mutex により後続呼び出しはその処理の完了を待ち、device の mask により二重実行を避けます。mask は成功前に立つので、失敗後の再試行もありません。出力は専用 scratch buffer に捨てられるため、生成結果に使う出力値は変更しません。

## 文書との照合

`docs/DETAILS.md` にはこの変数の説明はありません。`docs/AMD_HIP.md` は warm-up の目的、起動時スレッド、`=0` による無効化を説明しています。`docs/release-notes-0.2.1.md` は異なる architecture の GPU 構成で既定の warm-up を抑制し、`=1` / `=0` で上書きできるとしています。現在のコードは、明示値の先頭文字判定と、空値を含むそれ以外の値で architecture による自動判定を行う点でこの説明を具体化します。

リリースノートには、gfx1151 と gfx1201 の混在構成で報告者が `=0` により prompt の遅延を戻したこと、同一 architecture の R9700 2台では 32K prompt の測定（5 組）で 3,855 対 3,853 tok/s だったことが記載されています。これらは文書中の報告値であり、この調査で再測定・独立検証した値ではありません。

## 根拠

- `include/strata/prefill/warm_policy.hpp:17-28` — environment 値と architecture による自動判定、suffix を除いた比較。
- `include/strata/prefill/prefill.hpp:48-51` — API の目的、HIP 限定、無効化コメント。
- `src/prefill/prefill.cpp:1291-1358` — 環境変数の読み取り、static cache、architecture enumeration、ログ、GEMM 実行と HIP 以外の no-op。
- `src/prefill/prefill.cpp:1552` — `Prefill::init()` からの呼び出し。
- `src/program/generate.cpp:2153-2155,5532-5543` — 終了時 join と、GPU 識別後・arena 読み込み前のスレッド起動。
- `docs/AMD_HIP.md:527-533`, `docs/release-notes-0.2.1.md:48` — 既存の説明と測定値。
