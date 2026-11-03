# `DS4_STREAM_FORCE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DS4 の GGUF MoE decode で使う PCIe stream lane の自動判定を試験用に迂回し、request の CPU-lane picks のうち指定数を stream lane に割り当てます。値は真偽値ではなく文字列として保持され、各 request の pick 数に対応する文字を使います。通常の自動分割は stream の有利さを計測して判断しますが、非空値を設定するとその計測判定を使わず、設定した数を選びます（`src/dsv41/ds4_model.cu:9620-9623,9943-9955,10591-10594`）。

## 値と判定

| 状態・値 | Strata の扱い |
|---|---|
| 未設定 | `ln_force` は空のまま。lane の分割数は測定した cost、pick の RAM 状態、slot 数、decode の有利さ判定から自動決定する。 |
| 空文字 (`DS4_STREAM_FORCE=`) | `ln_force` は空。分割数の指定、測定キャッシュ迂回、force 用ログ表示は行わず、自動判定と同じ。環境変数が「存在する」ことだけを使う初期の one-GPU 判定では、unset と異なり過去の lane-off 記録を無視し、計画段階で自動的に off に戻す判定も抑止する。 |
| 非空文字列 | force モード。文字列全体の形式検証や数値 parse はしない。各 request で CPU-lane picks 数 `n` を求め、文字列の `n` 番目（0始まり）の文字があれば、その文字コードと `'0'` の差を `s` とし、`s` を `[0,n]` に clamp する。文字列が `n` 文字以下なら `s=0`。実際に stream lane が取る数はさらに device の slot 数以下となる。選ばれるのは picks の先頭 `s` 個。 |

したがって通常の ASCII 数字 `0`〜`9` はその数として扱われますが、文字列の先頭が常に使われるわけではなく、現在の request の `n` によって参照位置が変わります。数字以外も拒否されず、`'0'` との差が clamp されます。空白、大文字小文字、後続文字を含む文字列全体の妥当性検査はありません（`src/dsv41/ds4_model.cu:9943-9946`）。たとえば非空値でも、該当位置の文字が `'0'` 相当または文字列長が足りなければ、その request で stream lane に渡す数は 0 です。

## 有効になる条件

- lane 自体が有効である必要があります。`DS4_STREAM` が未設定または `atoi` 結果 0 なら lane allocation は即時に何もせず戻ります。`DS4_STREAM` が未設定の場合だけ `STRATA_DS4_STREAM` が参照され、設定があればそちらが優先されます。値 `2` は slots を保持する hold モードで、stream は行いません。したがって FORCE は lane を起動したり `DS4_STREAM=0` / hold を上書きしたりしません（`src/dsv41/ds4_model.cu:9711-9719,9753-9756,10619-10624`）。
- `lane_alloc()` は GGUF、`moe_token_path`、同期 decode でないことも要求します。その他の条件を満たさない場合は FORCE を読み取っても適用されません（`src/dsv41/ds4_model.cu:9753-9757`）。
- GPU staging slot、pinned host buffer、lane class と有効な timing cost が必要です。allocation / pinned slot の GPU address 取得 / timing に失敗すると、その GPU は CPU lane のみになります（`src/dsv41/ds4_model.cu:9760-9795,10431-10436,10460-10480,10555-10594`）。
- request ごとの stream 選択は `T == 1` の decode で `lane_take()` を呼ぶ経路です。window は別の `lane_take_win()` を呼び、force 文字列が非空だと同関数内の自動 stream 選択条件を通らないため、window picks の強制割当にはなりません（`src/dsv41/ds4_model.cu:9531-9538,10055-10069`）。
- one-GPU の自動経路判定は HIP build ではコンパイルされません。非-HIP build でも NVIDIA の単独 GPU 条件を満たす必要があります。ここで FORCE の環境変数が存在すると lane-times の以前の `off` 記録を無視しますが、これは他の lane 条件を代替しません（`src/dsv41/ds4_model.cu:6104-6127`）。

CLI 引数が `DS4_STREAM_FORCE` の値を上書きする読み取り箇所は確認できません。相互作用する設定は主に `DS4_STREAM` / `STRATA_DS4_STREAM` です。

## 実行時の詳細

初期化時の `one_gpu_path()` は環境変数の設定有無を確認します。続いて `lane_alloc()` が値を `ln_force` にコピーします。その後の setup は force モードでは過去の lane cost を読み込まず、計測結果を lane-times ファイルへ保存しません。ただし現起動で使用する cost を得るための timing は実施します。cost が有効なら `C.stream` を自動 verdict にかかわらず有効にします。lane の最終ログには ` - DS4_STREAM_FORCE` が付きます（`src/dsv41/ds4_model.cu:6120-6125,9753-9757,10520-10524,10555-10594,10631-10642`）。

`ln_force` はモデルの lane allocation 時に一度コピーされ、decode request ごとに環境を読み直しません。以後、プロセス環境を変更しても、そのモデルで保存済みの値は更新されません（`src/dsv41/ds4_model.cu:9753-9757,9916-9955`）。設定が有効でも読み込みに失敗した streamed expert はその token で使われず、stderr に `ds4: PCIe lane: reading a streamed expert failed - that token went without it` を一度だけ出します（`src/dsv41/ds4_model.cu:9916-9925`）。

## 根拠

- 環境値の有無による one-GPU lane-times 判定: `src/dsv41/ds4_model.cu:6104-6129`
- `DS4_STREAM` / `STRATA_DS4_STREAM` の選択と lane 無効判定: `src/dsv41/ds4_model.cu:9711-9719`
- lane の前提条件、値のコピー: `src/dsv41/ds4_model.cu:9753-9757`
- decode の force 分割と実際に選ぶ先頭 picks: `src/dsv41/ds4_model.cu:9916-9955,9961-9983`
- setup 時の cost cache、stream 有効化、結果ログ: `src/dsv41/ds4_model.cu:10520-10524,10555-10594,10616-10642`
- window 経路との違い: `src/dsv41/ds4_model.cu:9531-9538,10055-10069`
