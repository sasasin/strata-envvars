# `DS4_LAND`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

PCIe lane が CPU lane の expert を GPU にストリーム取得するとき、そのデータを staging slot ではなく層の recent slot に直接着地させるかを決めます。着地した expert は window 後の tick で VRAM の expert table に登録され、同じデータをもう一度コピーせずに recent slot に保持されます。`DS4_LAND` はその着地機能の選択値であり、PCIe lane 自体を有効にする設定ではありません。

## 値と判定

`src/dsv41/ds4_model.cu:6090-6093` の `env_tri()` が環境値を読みます。

| 環境値 | 判定 | `ln_land` |
|---|---|---|
| 未設定 | `-1`（指定なし） | `ln_one` に従う |
| 空文字 | `-1`（指定なし） | `ln_one` に従う |
| 空でない文字列を `atoi` で変換して 0 | `0` | 無効 |
| 空でない文字列を `atoi` で変換して非 0 | `1` | 有効 |

文字列全体の検証はありません。`atoi` が先頭の空白・符号・数字列を変換し、数字列がない値は 0 として扱われます。したがって `1tail` や `-2` は有効、`0tail` や `true` は無効です。`atoi` の整数変換範囲外の入力について Strata 独自の検査やエラー処理はありません。

## 有効になる条件

- `DS4_LAND` が未設定または空文字なら、既定値は `ln_one` です。`ln_one` は、HIP build ではない build で NVIDIA の単一 GPU・単一 group・単一 member かつ discrete GPU の場合に候補となります。さらに `DS4_STREAM`（未設定時は `STRATA_DS4_STREAM`）が `atoi` で 0 にならず、lane calibration が `off` でないことが必要です。`DS4_STREAM_FORCE` が設定されていれば calibration の `off` 判定を回避します (`src/dsv41/ds4_model.cu:6086-6128,9711-9719`)。
- 明示した `DS4_LAND=0` 相当の値は既定を無効化し、非 0 相当値は `ln_one` が false の場合でも `ln_land` を true にできます。ただし変数単独では PCIe lane を起動しません。lane は GGUF、lane 有効設定、MoE token path、非同期 decode などの条件を満たす必要があります (`src/dsv41/ds4_model.cu:6130-6138,9753-9755`)。
- recent slot は既定で、chunked prompt、GGUF、`ln_land`、lane 有効がそろうと各層 32 個分を要求します。`DS4_RECENT` が設定されていればその数値に置き換え、負数を含む値は 0 以上に制限されます。実際の slot は expert cache が有効で、対象層の空き容量が残る場合に割り当てられます (`src/dsv41/ds4_model.cu:2797-2802,5553-5564`)。明示的な `DS4_RECENT` は slot 数の指定を変えますが、PCIe lane の有効化条件は変えません。
- landing は `ln_land` が true であることに加え、層に recent slot があり、単一 member (`l.nm == 1`) で、expert が進行中の swap 対象でないときにだけ候補になります。request 内で参照中の expert、fill 中または他の landing が予約した slot は使いません。空 slot を優先し、なければ最も古く使われた slot を選びます (`src/dsv41/ds4_model.cu:9985-10011`)。

## 実行時の詳細

`one_gpu_path()` はモデル初期化中に `DS4_LAND` を `env_tri()` で読み、結果を `ln_land` に保持します。後続の `one_gpu_plan()` が one-GPU 経路を取り消す際にも `DS4_LAND` を読み直し、未設定扱いの場合に限り `ln_land` を false に戻します。明示値はこの既定経路の取り消しによって変更されません (`src/dsv41/ds4_model.cu:6130-6138,6143-6158`)。したがって環境値はこの初期化経路で最大 2 回評価されます。2 回目の評価後は `ln_land` に保存された判定が使われ、実行中の環境変更は反映されません。

ストリーミング対象の expert を割り当てる箇所で `land_dst()` が選んだ recent slot の GPU address を pull 先として返し、slot と pull の sequence/pick を記録します (`src/dsv41/ds4_model.cu:9958-9974,9985-10011`)。window 後の `rc_map()` は pull 完了・成功などを確認して slot の expert table を更新します。失敗や競合で条件を満たさない landing は採用されません (`src/dsv41/ds4_model.cu:8970-8992`)。

通常の設定値の読み取りに伴う `DS4_LAND` 固有の警告・終了経路はありません。GGUF の初期化では one-GPU decode path の状態を stderr に出し、`DS4_LAND` が明示設定されている場合は `, DS4_LAND=1` または `, DS4_LAND=0` を追記します (`src/dsv41/ds4_model.cu:6135-6138`)。landing の実績を観測する診断出力には、`DS4_RECENT_STATS` 設定時の終了時統計（streamed experts landed/tick）があります (`src/dsv41/ds4_model.cu:1924-1928`)。

## 根拠

- 値の読み取り・変換と default/override: `src/dsv41/ds4_model.cu:6090-6093,6130-6138`
- one-GPU 経路の条件と再判定: `src/dsv41/ds4_model.cu:6086-6128,6143-6158`
- `DS4_STREAM` の参照先と lane の入口条件: `src/dsv41/ds4_model.cu:9711-9719,9753-9755`
- recent slot の既定数と割当条件: `src/dsv41/ds4_model.cu:2797-2802,5553-5564`
- landing slot の選択・pull 結果の反映: `src/dsv41/ds4_model.cu:9958-9974,9985-10011,8970-8992`
- 観測ログ: `src/dsv41/ds4_model.cu:6135-6138,1924-1928`
