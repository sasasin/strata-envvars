# `--restart`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--restart` |
| 別名 | なし |
| 値 | 値を取らないフラグ。省略時は `False`。 |

## 役割

異なる設定で `strata launch` を実行するとき、同じ preset のサーバー、または指定 port を使っている別の `strata launch` サーバーを停止し、新しい設定で起動します。対話画面の再起動確認を省略し、非対話実行でも再起動を許可します。

## 使い方

```sh
strata launch --model q2_0 --context 64k --restart --no-tui
```

この例では q2_0 を context 64k で起動します。現在の選択と異なる設定が同じ preset または同じ port で稼働中なら、そのサーバーを置き換えます。

## 値と既定値

- `argparse` の `store_true` フラグで、値は指定しません。指定すると真、未指定なら偽です。短縮 alias はなく、重ねて指定しても真偽値以上の効果はありません。
- `--restart=false` のような値付き形式は定義されていません。
- `--plan` と併用すると計画表示の分岐で終了するため、再起動処理は実行されません。

## 実行時の動作

`run_launch` はこの値を `Runner(restart=...)` に渡します。対話画面を開く呼び出しでも同じ値を画面アプリへ渡します。`Runner.run()` は起動処理に入ると、モデルやエンジンの準備・設定構築より前に稼働中の launch を確認します。

- 同じ preset で同じ選択・port が既に稼働し、再チューニング中でもなければ、`--restart` の有無に関係なく既存サーバーを再利用します。停止・再起動はせず、稼働中のアドレスを返します。
- 同じ preset で異なる選択が稼働している場合、または別の launch profile が要求 port を使っている場合、`--restart` があれば確認なしで続行します。別 profile が同じ port を使う場合は、その profile を停止対象に登録します。自分の profile のサーバーは起動段階で停止します。
- 実際の停止は設定の準備後、エンジン起動時に行います。別 profile の停止には `runtime.stop(..., timeout=120)` と関連 tunnel の停止を試み、自分の profile の停止にも最大120秒の timeout を指定します。
- 別 profile の launch が異なる port で稼働中なら、`--restart` がなくても並行起動します。グラフィックスメモリーが足りず新しい起動に失敗する可能性がある旨を通知します。
- `--yes` は再起動の承認にはなりません。`--restart` がなければ、画面ありの経路では確認画面を一度表示し、`--no-tui` など確認画面のない経路では拒否します。

## 適用条件と副作用

このオプションが確認するのは `launch-` で始まる Strata launch profile の稼働状態とその port です。任意の外部プロセスを探して停止する指定ではありません。同じ port で別の launch サーバーを置き換える場合、そのサーバーは新しい設定の起動前に停止されます。画面の説明と利用者向け資料は、処理中の応答が止まることを明記しています。

`--retune` を併用すると、チューニング測定のため同じ profile のサーバーが起動処理より前に停止される場合があります。測定の終了後は新設定で起動する通常の経路に戻ります。

## 出力とエラー

- `--restart` なしで確認画面もない状態のまま競合するサーバーがあると、エラーを返します。通常出力は `strata: ...` を stderr に出し、終了コードは `6` です。JSON 出力では `ok: false` とエラーコード・文面を JSON で出力します。
- 対話画面で再起動をキャンセルすると、稼働中のサーバーを維持し、終了コード `130` のキャンセルエラーになります。
- 対象サーバーの停止に失敗すると、停止できなかった旨と `strata launch --stop` の案内を出し、終了コード `6` で失敗します。
- 再利用できた場合は `Already serving these choices; nothing was restarted.` とアドレスを表示します。通常の起動成功時は `Strata is serving.` と接続先を表示します。

## 根拠

- `strata_cli/launch/cmd.py:132-134` — parser の `store_true` 定義、説明、`--yes` と同一選択時の注意。
- `strata_cli/launch/cmd.py:688-716,780-787` — 対話・非対話の分岐と `Runner` への値の伝達、失敗表示。
- `strata_cli/launch/cmd.py:636-641,801-811` — stderr/JSON のエラー出力、起動結果・再利用結果の表示。
- `strata_cli/launch/runner.py:2011-2044` — 起動順序と、稼働確認から準備・起動までの流れ。
- `strata_cli/launch/runner.py:1460-1480,1505-1539` — 対象となる稼働 profile、同一設定の再利用、port 競合、確認・拒否条件。
- `strata_cli/launch/runner.py:1546-1572` — 同一 port の別 profile と自身の profile の停止、および停止失敗経路。
- `strata_cli/launch/runner.py:1396-1415` — 再チューニング時の稼働サーバー停止。
- `strata_cli/launch/app.py:280-319` — 対話画面への伝達と再起動確認画面。
- `docs/TERMINAL_LAUNCH.md:69,77` — 利用例、応答中断・`--yes` との関係、異なる port の扱い（利用者向け補助資料）。

調査範囲は上記 commit の Terminal CLI ソースと同 revision の利用者向け文書です。別 OS・外部プロセス・リリース済み配布物の個別挙動は実行確認していません。
