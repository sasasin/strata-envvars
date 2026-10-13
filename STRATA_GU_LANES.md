# `STRATA_GU_LANES`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。調査対象リポジトリの作業ツリーは clean。外部ライブラリの環境変数の動作は対象外。

## 役割

SYCL ポートの grouped expert kernel で、gate/up の各出力行を処理する lane 数を選びます。許可値は 4、8、16、32 で、lane 数に応じて 256 work-item の work-group 内で処理する行数が `256 / lanes` に変わります。これはカーネルの起動構成を選ぶ設定で、expert の数やモデルの値を指定するものではありません。

## 値と判定

値は `std::atoi` で整数に変換され、変換後の値が 4、8、16、32 のいずれかなら採用されます。それ以外はコンパイル時定数 `kExpertLanes` に戻ります。未設定時も同じ定数が使われます。`STRATA_EXPERT_LANES` がビルド時に別途定義されない場合の定数は 8 です。

| 環境値 | 判定結果 |
|---|---|
| 未設定 | `kExpertLanes`（通常は 8） |
| `4`, `8`, `16`, `32` | その整数を採用 |
| 空文字、`0`、`3`、`64`、負数など | `kExpertLanes` に fallback |
| `8foo`, `16.0`, ` 4` など | `atoi` が先頭から変換した整数が許可値なら採用。全体一致は検査しない |
| 数字で始まらない文字列 | `atoi` の結果 0 となり fallback |

大小文字比較や空白除去、厳密な文字列 parse はありません。数値に変換できる接頭部だけが使われます。

## 有効になる条件

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp` の SYCL 実装にある `native_expert_grouped()` の gate/up kernel 経路で参照されます。CUDA/HIP の別実装へこの環境変数が適用される根拠は見つかりませんでした。
- `native_expert_grouped()` が gate/up 計算を実行し、`launch_gu()` が lane kernel を選ぶ経路で有効です。通常の `kSplit<TG>` でない形式と、split 形式でも旧 kernel または multi-entry を使わない場合に lane kernel を呼びます。
- `STRATA_EXPERT_SPLIT` 等により split multi-entry kernel が選ばれた形式では、この変数ではなく multi-entry kernel が使われます。
- `STRATA_GU_LANES` と `STRATA_DOWN_LANES` は別々に読み取られます。この変数が down projection の lane 数を変えることはありません。

## 実行時の詳細

`gu_lanes()` の関数内 static 定数が `lanes_env("STRATA_GU_LANES")` の戻り値を保持します。したがって環境値の読み取りはプロセス内で初めて `gu_lanes()` が呼ばれた時で、その後プロセス内で環境を書き換えても再評価されません。値を選んだ後、`launch_gu_lanes()` は lane 数ごとのテンプレート kernel（4/16/32、その他は8）を起動します。行数は `256 / lanes` であり、グリッドの X 寸法は gate/up の幅 `2 * L.n_ff` をこの行数で割って切り上げます。

コードは設定値を示す専用ログを出しません。`docs/INTEL.md` は gate/up 8 または16と down 4または8の組み合わせを Coder の2 prompt・各2 runsで比較し、verify round が37.7–38.6 msだったと記しています。同資料は token/s の差が draft acceptance に由来すると述べ、既定の 8/8 を維持しています。これは同資料に記録された測定条件での結果であり、性能保証ではありません。

## 根拠

- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:794-801` — コンパイル時既定 `STRATA_EXPERT_LANES`（未定義なら8）と `kExpertLanes`。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4100-4109` — `atoi`、許可値、fallback、`gu_lanes()` の static cache。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4111-4132` — lane 数に応じた gate/up kernel 起動と行数・grid 算出。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4176-4194` — `launch_gu()` が lane kernel と multi-entry kernel を選ぶ条件。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5052-5057,5074-5079,5130-5135` — grouped expert 呼び出しの有効範囲と gate/up kernel dispatch。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:4210-4223,5229-5235` — down kernel が独立した `down_lanes()` を使うこと。
- `sycl/CMakeLists.txt:209` — SYCL の kernel target に `iq_kernels` が含まれること。
- `docs/INTEL.md:545-547` — lane 設定の記述と測定条件。
