# `FNX_PF_TIMING`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Flash-Next split engine の prefill 経路で、バッファ確保量、expert staging buffer、prefill pass の所要時間と転送量を stderr に出す診断用スイッチです。計算方法や prefill の選択を切り替える処理はなく、出力条件だけを変えます。直接参照は `src/split/src/prefill.cu` の3箇所で、`FNX_PF_TIMING` を使う別の Strata コード経路は見つかりませんでした。

## 値と判定

`fnx::env_flag()` は `env_int(name, 0) != 0` です。`env_int()` は `std::getenv()` の値全体を、符号付き10進整数として `strtoll()` で読みます。先頭に `+` または `-` を付けられますが、少なくとも1桁の数字が必要で、末尾まで数字でなければなりません。`long long` の範囲を超える値も拒否されます。

| 値 | 判定 |
|---|---|
| 未設定 | `0` 扱いで無効 |
| `0`, `+0`, `-0` | 無効 |
| `1`, `+1`, `-1`, その他の範囲内の非ゼロ整数 | 有効 |
| 空文字、空白を含む値、`1x`、`1.0`、整数範囲外 | 無効値として parse error。fallback せず例外 |

文字列の大文字小文字は関係しません。空白の trim、真偽値文字列の解釈、CLI 引数による上書きはありません。

## 有効になる条件

この設定は `src/split/src/prefill.cu` の split engine prefill 実装で参照されます。CUDA/HIP 共通のこの実装に backend 別の `FNX_PF_TIMING` 条件分岐はありません。Engine を作ると prefill buffer を確保し、その後 staging buffer を確保する経路があり、prefill pass を実行した経路では pass ごとの出力も行います。staging buffer の出力は、そのカードで `stage_bytes` が0でない場合に限られます。pass 出力は prefill pass が正常に最後まで到達した場合に限られます。

この変数自体に値があっても、該当する診断箇所に到達しなければその行は出ません。特に pass timing は `Engine::prefill()` が `prefill_pass()` を呼び出す実行経路に限られます。`FNX_PREFILL` などによる上位の prefill 経路選択は別設定であり、この変数はその選択を変更しません。

## 実行時の詳細

`prefill_alloc()` は Engine 構築中に呼ばれ、カードごとの prefill buffer 確保後に `FNX_PF_TIMING` を読みます。有効なら `prefill buffers on card ...` と、確保した MiB 数および確保前の空き MiB 数を stderr に出します。`prefill_stages()` も Engine 構築中に呼ばれます。staging 領域が必要なカードでは確保後に値を読み、有効なら `prefill on card ...` と pass 数・staging MiB 数を出します。これら2箇所は `env_flag()` を呼ぶたびに環境を読み直し、キャッシュしません。

`prefill_pass()` の終端では関数内の `static const bool timing` として初回到達時に値を一度だけ読みます。以後の pass ではこの判定を再利用するため、その後にプロセス環境を書き換えても pass timing の有効・無効は変わりません。有効なら stderr に開始位置、chunk 数、row 数、総時間、embed + upload 時間、enqueue までの時間、draft layer の時間を出します。staging 中は同じ行にカードごとの expert コピー量と in-place 読み取り量も追記します。ログの時間値はここに記載された計測区間の値で、外部ライブラリや GPU driver の内部動作を説明するものではありません。

無効な設定値は `env_int()` が `FNX_PF_TIMING: '<値>' is not a whole number` という `std::runtime_error` を送出します。値を読むタイミングで起きるため、Engine 初期化中の読み取りなら初期化が失敗します。`fnx_run` は例外を `fnx_run: ...` と stderr に出して終了コード1を返し、`sfnx` の Engine 構築経路は `sfnx: failed: ...` を stderr に出して終了します。正常な値のとき、この変数自身が警告や終了を起こす分岐はありません。

## 根拠

- 候補一覧には `FNX_PF_TIMING` が載っています（調査対象リポジトリ `docs/envvars/000_envvers.md:585`）。ソース全体の完全一致検索では `src/split/src/prefill.cu:855,939,1353` の3参照を確認しました。
- 値の読み取りと整数全体の parse、未設定時既定値、無効値エラーは `src/split/src/env.hpp:15-22,33-40,51-52`。
- buffer 確保後の診断出力は `src/split/src/prefill.cu:625-635,853-856`、staging 領域がない場合の skip と staging 診断は同 `:929-940`。
- prefill の staging 条件と chunk/pass 実行は `src/split/src/prefill.cu:982-1035`。pass の完了待ち、timeout/ring error と timing 出力は同 `:1317-1364`。
- Engine 構築から buffer/staging 確保への呼び出しは `src/split/src/engine.cu:275-316,347-349`。`fnx_run` の MTP 経路で `FNX_PREFILL` が prefill を選ぶ分岐は `src/split/tools/fnx_run.cpp:1003-1019`。
- `fnx_run` の例外表示と終了コードは `src/split/tools/fnx_run.cpp:1364-1373`。`sfnx` の Engine 構築例外経路と失敗時の stderr・終了処理は `src/split/tools/sfnx.cpp:1032-1035,1050-1062`。
- Strata の docs を完全一致検索しましたが、`FNX_PF_TIMING` の動作説明は見つからず、追加の資料との照合はできませんでした。
