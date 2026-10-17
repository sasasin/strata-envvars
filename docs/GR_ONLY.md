# `GR_ONLY`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

Metal の `gr2_parity --bench` 開発用ベンチマークで測定対象の dispatch を絞ります。`gr2_parity` は Strata の通常実行経路ではなく、`metal/tests/gr2_parity.cpp` にあるテスト用プログラムです。この変数を読む Strata 所有ソースはこの箇所だけで、生成・推論処理を制御する読み取りはありません。

## 値と判定

ベンチマークが組み立てた dispatch 列は down/up の順で交互に並びます。`getenv()` の設定有無を調べ、設定されていれば文字列全体を大文字小文字を区別して `"up"` と比較します。

| `GR_ONLY` | 動作 |
|---|---|
| 未設定 | dispatch 列を絞らず、down と up の両方を測定 |
| `up` と完全一致 | 各ペアの up dispatch（奇数 index）のみを測定 |
| その他の設定値 | 各ペアの down dispatch（偶数 index）のみを測定 |

したがって空文字、`UP`、`down`、`1` も設定値として認識されますが、いずれも down dispatch のみを残します。値の parse、空白除去、数値変換はありません。

## 有効になる条件

絞り込み処理は `argv[1]` が `--bench` のときだけ通るベンチマーク分岐にあります。通常の parity 検証では `GR_ONLY` は参照されず、ベンチマークの引数も環境変数の値も dispatch 選択に影響しません。このソースは Metal テスト用プログラムに属し、通常の Strata 実行ファイルの環境設定として使われる実装は確認できませんでした。

## 実行時の詳細

ベンチマークは各設定の dispatch を96個作り、その後 `GR_ONLY` を読みます。未設定なら全件を保持します。設定済みなら `std::string(only) == "up"` の真偽値を開始 index にし、2個おきに dispatch を新しい列へコピーします。`up` の場合は index 1 から、それ以外の場合は index 0 から始めるため、選択後に `cx.warm()` と7回の `cx.run()` に渡される列が変わります。各出力行ではその実行時間を96で割って表示します。したがってこの値は測定に使う GPU dispatch と表示時間に関わります。

環境変数はベンチマークのこの箇所で読み取られます。static cache はなく、プロセス起動後に環境を書き換える挙動はこのコードからは確認できません（このプログラムは通常1回のベンチマーク実行内で判定します）。このベンチマークを起動する親プロセスが環境変数を転送・変更する Strata 所有コードも見つかりませんでした。

## 根拠

- `metal/tests/gr2_parity.cpp:30-31`: `--bench` 引数の判定。
- `metal/tests/gr2_parity.cpp:109-123`: ベンチマーク分岐での dispatch 列生成、`GR_ONLY` 判定・絞り込み、その後の warm-up、計測、表示。
- `rg -n --hidden --glob '!.git/**' 'GR_ONLY' .` の調査対象 HEAD 内の結果は `metal/tests/gr2_parity.cpp:112` のみ。
