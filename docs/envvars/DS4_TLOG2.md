# `DS4_TLOG2`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

## 役割

DeepSeek-V4.1 エンジンの非同期 MoE token 経路で、expert 処理中のホスト側経過時間を3区間に分けて集計し、プロセス終了時に標準エラーへ平均時間を出す診断用スイッチです。計測対象の区間は gate/up の発行、CPU lane の応答待ち、down の発行です。変数は expert 計算や経路選択を変えず、時刻取得と集計、終了時ログだけを有効にします。

## 値と判定

| 状態 | Metal build | CUDA/HIP build |
|---|---|---|
| 未設定 | 無効 | 無効 |
| 空文字を含む任意の設定値 | 有効（設定有無だけを見る） | 無効 |

Metal では `ds4_dbg("DS4_TLOG2")` が `std::getenv(name) != nullptr` を返します。値の文字列比較や数値変換はなく、`1` 以外や空文字でも有効です。CUDA/HIP など Metal 以外では同 helper がコンパイル時定数 `false` を返すため、環境変数を設定しても無効です。CLI 引数や他の環境変数による上書きはありません。

## 有効になる条件

- DeepSeek-V4.1 の `strata-dsv41` エンジンがビルドされて実行される必要があります。CMake の `STRATA_BUILD_DSV41` は既定で OFF です。
- この計測箇所は `wp.async` かつ `T == 1` かつ `moe_token_path` のときだけ通ります。通常の `plan_window()` では `wp.async = par || (!sync_decode && T <= async_max_t)` です。Metal では `DS4_ASYNC` 未設定時は同期 decode、設定時は非同期 decode が選ばれ、`DS4_ASYNC_T` の既定値は 8 です。別の並列 window 経路は `wp.async` を直接 true にします。
- `moe_token_path` はモデル初期化時に一度決まり、`DS4_MOE_TOKEN` 未設定なら有効、設定時は `atoi(value) != 0` の場合に有効です。`DS4_MOE_TOKEN=0` や数値に変換できない文字列では、この計測箇所を含む token 経路を通らず、別の `win_experts` 経路になります。
- `DS4_TLOG2` 自体は計測箇所に初めて到達した時に `static const bool` として評価されます。そのため、その評価後にプロセス環境を変えても反映されません。

## 実行時の詳細

計測は `now_ms()`（`steady_clock` のミリ秒）で時刻を取り、各到達について次の差を静的カウンターに加算します。

1. `moe_gate_up()` 呼び出しの前後: `gate_up`
2. その直後から CPU lane の応答を待つ `wait_seq()` の後まで: `cpu_wait`。group lead 以外は `wait_seq()` を呼ばないため、その側の区間には実質待ち時間が入りません。
3. `wait_seq()` 後から `moe_down()` 呼び出し後まで: `down`

`atexit` handler は有効な `DS4_TLOG2` でこの経路に初めて入った時に登録されます。正常終了時などのプロセス終了処理で、処理回数と1回あたりの平均を次の形式で stderr に出します（各時間は小数第2位まで）。`stages` が0の場合の除算は0として出力します。

```text
tlog2: <回数> stages | host ms a stage: gate_up <ms>  cpu_wait <ms>  down <ms>
```

環境変数が未設定、Metal 以外の build、同期 decode、または token 経路が無効の場合、このログは登録されません。対象処理が途中でエラーを返した場合、`DS4_TLOG2` 固有の警告やエラー出力、終了コード変更はありません。これはホスト側の区間時間であり、GPU 処理時間そのものを個別に測る実装ではありません。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — `ds4_dbg` は Metal で設定有無を確認し、それ以外では常に false。
- `src/dsv41/ds4_model.cu:1126-1136` — Metal の同期 decode 判定、`DS4_MOE_TOKEN` の既定値と判定、`DS4_ASYNC_T` の既定値。
- `src/dsv41/ds4_model.cu:9565-9592` — `wp.async` の条件。
- `src/dsv41/ds4_model.cu:10301-10328` — 非同期 MoE 経路と `T == 1 && moe_token_path` の条件。
- `src/dsv41/ds4_model.cu:10342-10364` — `DS4_TLOG2` の static cache、3区間の計測、終了時 stderr ログと集計。
- `CMakeLists.txt:906-920` — DeepSeek-V4.1 engine と `strata-dsv41` の build option（既定 OFF）。
