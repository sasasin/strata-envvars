# `STRATA_IQ3S_GU_ROW_REUSE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata の作業ツリーは `main...origin/main` で clean。

## 役割

SYCL の native grouped expert 処理で IQ3_S の gate/up 行を計算するとき、通常の grouped kernel の代わりに 2 行ずつ扱う row reuse kernel を選びます。この kernel は各行対について activation の量子化値を一度作り、2 行の重みとの積に使います。IQ3_S の全経路を切り替える設定ではなく、以下の device・レイアウト・lane 条件を満たす dispatch だけに適用されます。

候補一覧 `docs/envvars/000_envvers.md` に掲載されています。Strata ソース全体の名前検索では、実読込 helper 呼び出しが `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4988` に 1 箇所ありました。ほかの名前参照は `docs/INTEL.md:533` の説明です。

## 値と判定

値は `strata::bm_default_on()` が環境から読みます。文字列全体や数値として parse せず、設定値が空でなければ先頭文字だけで判定します。

| 環境値 | helper の判定 |
|---|---|
| 未設定または空文字 | Battlemage なら有効、それ以外は無効 |
| 空でない値の先頭が `0` | 無効（例: `0`, `0abc`） |
| 空でない値の先頭が `0` 以外 | 有効（例: `1`, `2`, `true`, `false`, `abc`） |

大文字小文字、空白、後続文字は検査されません。無効な値を示す専用 fallback・警告・エラー処理はありません。`bm_default_on` は値が空でない場合に先頭文字の判定を返し、値が未設定または空の場合だけ device 世代と既定値を使います（`sycl/include/strata/sycl_queue.hpp:159-166`）。

## 有効になる条件

helper の判定が有効でも、次をすべて満たさなければ row reuse kernel は呼び出されません。

- `STRATA_GRID_SLM` が 0。ソース内で未定義時の既定値は 0 です。1 でビルドすると、この環境変数を読むコードも含めてコンパイル対象から外れます。
- native grouped expert の gate/up 型が IQ3_S（`L.gu_type == 21`）。
- `STRATA_OLD_IQ_MMVQ` による旧 kernel 選択が無効で、`STRATA_EXPERT_SPLIT` による multi kernel 選択も無効。
- `STRATA_GU_LANES` の解決値が 8。値は `atoi` で変換され、4/8/16/32 以外なら `STRATA_EXPERT_LANES` の compile-time 値に戻ります（ソース既定値は 8）。
- layout が `L.n_embd == 2560` かつ `L.n_ff == 640`。
- SYCL device が Battlemage と判定される。

設定値 `1` などで helper を有効にしても、非 Battlemage device では最後の条件で不採用になります。モデルや CLI 引数が環境変数の値を上書きする処理は見つかりませんが、選択された model/layout が gate/up 型や寸法の条件に影響します。

## 実行時の詳細

`launch_gu<TG>()` は `TG == 21` のときだけこの設定を調べ、条件を満たすと stderr に `strata: IQ3_S two-row GU reuse enabled (8 lanes, SIMD16, direct activation reads)` を出して `launch_gu_row_reuse<21>()` を起動します。row kernel は gate/up の 2*n_ff 行を走査し、各行対で `rows_dot_reuse()` を呼びます。同関数は `M::acts()` で activation 側の値を作り、2 行それぞれの重みを用いて積和します（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4721-4765,4768-4819,4822-4852,4981-4999`）。

helper の判定は `launch_gu<TG>()` 内の関数ローカル `static const bool` に保存され、最初の評価後は環境の変更で再評価されません。Battlemage 既定判定を使う場合、helper に渡る device は最初の呼び出し時の device です。`STRATA_GU_LANES` も `gu_lanes()` の static 値として初回に解決されます（`sycl/src/kernels/cuda/iq_kernels.dp.cpp:4863,4986-4991`）。

条件に合わない場合は後続の通常 dispatch へ進みます。IQ3_S の `STRATA_IQ3S_GU_SLM` 経路は別途評価され、その後も該当しなければ lane kernel または `STRATA_EXPERT_SPLIT` の multi kernel を選びます（同ファイル `:5001-5026`）。この変数固有の値エラーや失敗終了は実装されていません。通常 dispatch 後には共通の `check("native_expert_grouped/gu")` がありますが、環境値に応じた独自の終了処理ではありません（同ファイル `:6126-6135`）。

## 根拠

- helper の値解釈、Battlemage の既定値: `sycl/include/strata/sycl_queue.hpp:159-166`。
- `STRATA_GRID_SLM` の compile-time 既定値と、環境変数の読み取り・dispatch 条件・有効ログ: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:452-457,4981-4999`。
- lane 値の変換と cache: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4855-4864`。
- 2 行 kernel の処理と起動: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4721-4852`。
- 後続 dispatch と共通 check: `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5001-5026,6126-6135`。
- `docs/INTEL.md:518-540` は Battlemage 向け制御一覧と複数制御をまとめた測定条件を記載しています。測定値は複数の build/runtime control をまとめた比較のため、この環境変数単独の効果としては記載していません。
