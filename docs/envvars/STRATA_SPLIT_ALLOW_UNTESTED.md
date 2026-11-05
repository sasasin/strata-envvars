# `STRATA_SPLIT_ALLOW_UNTESTED`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

Strata の all-cards split engine を選ぶとき、通常は実行実績がないカード数・カード architecture・context を理由に拒否する判定を通過させます。変数は「未テスト」判定だけを許可し、split engine を必ず起動するスイッチではありません。CLI の `strata split-engine apply` と Terminal の launch で読み取られます。

## 値と判定

3つの読み取り箇所すべてで、環境変数の文字列全体が `"1"` と等しい場合だけ `allow_untested=True` になります。数値変換や trim はありません。

| 環境値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1` | 有効 |
| `0`、`true`、`01`、`1 `、その他 | 無効 |

CLI 引数や設定ファイルの値がこの値を上書きする仕組みはありません。`--split-engine` / run config の `split_engine` と `STRATA_SPLIT_ENGINE` は起動モードを別に選び、`STRATA_SPLIT_ENGINE` が空でないときは設定値より優先されます。この文書の変数はそのモードを変更しません。

## 有効になる条件

通常は、カード数が記録済みの実行数でない、カード architecture がテスト済みでない、または context が 131072 を超えると、判定を拒否します。この変数が正確に `1` なら、該当条件を拒否理由にせず、成功時の決定に未テスト項目を記録します。複数の未テスト条件があれば各項目が記録されます。

許可されない条件は引き続き拒否されます。たとえば Linux 以外、カードが2～4枚でない、ベンダーやカード型が混在、AMD のビルド対象外 architecture、未対応の expert/model shape や tensor type、VRAM/RAM 不足、engine binary・draft layer・vocabulary file の不足、または他の起動条件不成立は、この変数では解消されません。Terminal の Auto mode にある追加ゲートも残ります。AMD の未実行 architecture は `--split-engine on` のときに別途許可されますが、この変数だけで同じ扱いにはなりません。

## 実行時の詳細

環境値は各呼び出し時に Python の `os.environ.get` から読みます。プロセス中に環境を書き換えた場合、まだ呼ばれていない読み取りには新しい値が使われます。Terminal runner の `split_expected()` は結果を runner インスタンス内に cache するため、その事前判定を再利用する箇所では後の環境変更は反映されません。一方、設定を適用する `apply_split_engine()` は別途その時点の値を読みます。プロセス起動時に一度だけ固定する cache はありません。

- CLI の `strata split-engine apply --config ...` は判定を行い、split を選べた場合だけ `--out` に変換後の config を書きます。human 出力では判定行を表示し、通常の拒否は `Using the normal layer split: ...` の形式です。判定自体が通常の拒否を返してもこのサブコマンドは終了コード 0 です。
- Terminal launch は、判定に成功すると all-cards split 用 config に切り替え、`Using the all-cards split engine on N cards (...: not tested).` のように未テスト項目を含む行を通知します。Auto で拒否された場合は通常その理由を黙って通常の layer split にします。明示的な `on` では拒否理由を一行で通知します。
- `apply_to_config()` は判定を通ると config を split 用に書き換えます。例外時は元の config に戻し、launch は通常の layer split を使います。

## 根拠

- 全参照と完全一致判定: `strata_cli/split_cmd.py:43`, `strata_cli/launch/runner.py:1569-1572,1721`。
- CLI の config 出力・表示・終了コード: `strata_cli/split_cmd.py:25-33,41-59`。
- runner の事前判定 cache と適用時の読み直し: `strata_cli/launch/runner.py:1544-1575,1696-1736`。
- 判定引数の伝播と例外時の復元: `strata_control/split_engine.py:476-489,492-565,631-656`。
- 未テスト項目だけを許可し、成功 Decision に記録する箇所: `strata_control/split_engine.py:190-261`。
- モードの既定値と `STRATA_SPLIT_ENGINE` / run config の優先順位: `strata_control/split_engine.py:395-409`。
- 対象条件、Linux 限定と他の拒否条件: `strata_control/split_engine.py:190-261,497-565`。
- 通常時と明示 `on` 時の適用・拒否ログの扱い: `strata_control/split_engine.py:476-489,631-656`; Terminal 側通知: `strata_cli/launch/runner.py:1722-1736`。
