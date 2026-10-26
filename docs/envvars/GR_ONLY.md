# `GR_ONLY`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

`GR_ONLY` は Metal の `gr2_parity` テストプログラムにあるベンチマーク用環境変数です。`--bench` 実行時に、2-dispatch hyper-connection read の計測対象を down または up の dispatch に絞ります。Strata の通常の engine 実行を制御する変数としての読み取りは、この HEAD では確認できません。

## 値と判定

値を数値や真偽値として parse せず、`getenv()` が null かどうかと、設定値全体が小文字の `up` と完全一致するかを調べます。

| 状態 | `gr2_parity --bench` での動作 |
|---|---|
| 未設定 | dispatch を絞らず、down と up の両方を計測 |
| `up` | up dispatch だけを計測 |
| `down`、空文字、`UP`、その他の文字列 | down dispatch だけを計測 |

空文字を含む何らかの値が設定されていれば絞り込みが働きます。`up` 以外の値を `down` として検証するわけではなく、単に up 以外の偶数番 dispatch を残す実装です。

## 有効になる条件

この分岐は `metal/tests/gr2_parity.cpp` の `bench` 条件内にだけあります。`bench` は第1コマンドライン引数が厳密に `--bench` と一致する場合に true です。通常の parity 実行では `GR_ONLY` を読みません。

## 実行時の詳細

ベンチマーク時、各設定について `enc()` が down dispatch を追加し、その直後に up dispatch を追加します。96 組を追加した後、`GR_ONLY=up` ならインデックス1から2つおきに選び up dispatch を残し、それ以外の設定値ならインデックス0から2つおきに選び down dispatch を残します。その dispatch 群を warm-up し、7回計測した時間を96で割って表示します。環境変数は static cache されず、このベンチマークの各設定ループで読み直されます。ソースには値を変更する処理、子プロセスへの転送、環境変数に関するログはありません。

## 根拠

- `metal/tests/gr2_parity.cpp:1-6` はファイルを Metal の hyper-connection read の parity / benchmark プログラムとして説明しています。
- `metal/tests/gr2_parity.cpp:30-35` は `--bench` の判定とベンチマーク時のセット数を定義します。
- `metal/tests/gr2_parity.cpp:88-108` は down dispatch の後に up dispatch を追加します。
- `metal/tests/gr2_parity.cpp:109-123` は `GR_ONLY` の読み取り、完全一致判定、dispatch の間引き、および計測を行います。
- HEAD 内の `GR_ONLY` 完全一致検索では、この読み取り以外の参照は見つかりませんでした。したがって、ここに記した動作はテスト用ベンチマークの範囲に限られます。
