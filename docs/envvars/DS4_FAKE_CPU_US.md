# `DS4_FAKE_CPU_US`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DSV4.1 の Metal 経路で、CPU expert の実計算を省略したときに、代わりに指定したマイクロ秒数だけ待つための診断用変数です。CPU expert を計算する通常経路の速度や処理を設定するものではありません。ソースコメントも `(timing only)` としています。

## 値と判定

| 状態 | 判定と動作 |
|---|---|
| 未設定 | `ds4_dbg("DS4_FAKE_CPU_US")` が false。待機しない |
| 設定あり（空文字を含む） | Metal では設定有無だけを調べるため true。その後 `std::atoi` で整数化し、その値を `std::chrono::microseconds` に渡して `sleep_for` を呼ぶ |
| 整数として読める接頭部を持つ文字列 | `atoi` が先頭の整数部分を変換する（先行空白と符号を許し、後続の非数値部分は検査しない。例: `12xyz` は 12、`  -3tail` は -3） |
| 数字に変換できない文字列・空文字 | `atoi` は 0 を返すため、0 マイクロ秒の待機を要求する |
| 負の整数 | 負値をそのまま `microseconds` に渡す。Strata は clamp や拒否をしない |

数値全体の妥当性、範囲、オーバーフロー時の値は Strata で検証していません。`atoi` は呼び出しごとに行われ、結果を保存する cache はありません。

## 有効になる条件

- `STRATA_METAL` を定義したビルドであること。`src/dsv41/ds4_launch.h` では Metal のときだけ `ds4_dbg(name)` が `getenv(name) != nullptr` を行い、それ以外では常に false を返すため、CUDA/HIP ではこの環境変数の分岐は有効になりません。
- CPU に割り当てられた expert entry（`ents`）があること。entry がないと該当ブロックに入りません。
- `DS4_SKIP_CPU` が有効であること。無効なら `cpu_experts(...)` を実行し、`else if` にあるこの変数は参照されません。`DS4_SKIP_CPU` は設定値の内容でなく設定有無で判定され、初回評価結果が関数内の `static const bool` に保存されます。

このため `DS4_FAKE_CPU_US` 単独では CPU 計算を止めません。実装箇所は Metal 条件付き処理にあり、Strata のこの分岐に CLI 引数による上書きはありません。

## 実行時の詳細

ホスト側で routing 結果を処理し、GPU expert の処理を終えた後、`ents` が空でない場合に CPU lane に進みます。Metal では `ds4_metal_kick()` の後に `DS4_SKIP_CPU` を判定します。CPU lane を省略しない場合は `cpu_experts` を呼びます。省略する場合に限り、`DS4_FAKE_CPU_US` が設定されていれば `atoi(getenv(...))` の値を microseconds として `std::this_thread::sleep_for` に渡します。その後は `h_part` の初期化・combine と GPU へのコピーが続きます。したがって、この環境変数が行うのは待機要求であり、CPU expert の結果を計算・補完する処理ではありません。

`DS4_FAKE_CPU_US` 自体は各該当 lane 呼び出しで設定有無と値を読み直します。プロセス起動時や最初の呼び出し時に値を cache する実装ではありません。対して `DS4_SKIP_CPU` は初回評価時に cache されます。該当コードにこの変数専用のログ、警告、終了・失敗処理はありません。待機時間の実測値も Strata の文書から確認できませんでした。

## 根拠

- `src/dsv41/ds4_launch.h:30-36` — `ds4_dbg` は Metal ビルドでは環境変数の設定有無を返し、非 Metal ビルドでは常に false。
- `src/dsv41/ds4_model.cu:10413-10416` — 複数デバイスの host-routed path を拒否し、ここから先は `nm == 1` の host-routed 経路。
- `src/dsv41/ds4_model.cu:10417-10430,10462-10470,10555-10564` — host routing 後の GPU/CPU expert の振り分け、`ents` がある場合の処理、`DS4_SKIP_CPU` と待機分岐。
- `src/dsv41/ds4_model.cu:10567-10582` — 分岐後の `h_part` 初期化、combine、GPU へのコピー。
- `src/dsv41/ds4_model.cu:10561-10563` — `DS4_SKIP_CPU` の static cache と `DS4_FAKE_CPU_US` の `atoi` / `sleep_for`。同ファイル内のこの名前の参照はこの1箇所。
