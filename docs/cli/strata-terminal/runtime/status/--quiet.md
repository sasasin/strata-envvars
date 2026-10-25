# `--quiet`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata runtime status` |
| オプション | `--quiet` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

成功時の人間向け status 行を表示せず、終了コードで結果を扱いたい場合に使います。`--output json` と併用した場合は JSON を抑制しません。

## 使い方

```sh
strata runtime status --profile four-gpu --quiet
```

JSON で状態を受け取る場合:

```sh
strata runtime status --profile four-gpu --quiet --output json
```

## 値と既定値

値を取らず、指定すると `True` になります。省略時は quiet ではありません。`runtime status` parser には `--quiet` が個別宣言されていませんが、one-shot parser 群に後から追加されており、このコマンドでも有効です（`strata_cli/cli.py:213-215,508-515`）。同じフラグを繰り返しても真偽値のままです。値を伴う形式は定義されていません。

## 実行時の動作

`runtime status` は指定 profile の保存済み所有状態を確認します。状態ファイルがなければ `stopped`、所有 host の lease が有効でなければ `stale` を返し、lease が有効なら owner host に認証済み status 要求を送ります（`strata_control/runtime.py:444-455`）。status 要求は host 側の状態を読み取ります（`strata_control/management.py:231-234`、`strata_control/runtime.py:1166-1172`）。このオプション自体がサーバーを起動・停止する処理はありません。

人間向け出力を選び `--quiet` を付けると、main は status の実行中に stdout を一時捕捉し、成功コードなら表示せず破棄します。失敗コードで捕捉内容がある場合は stderr に出し直します。捕捉上限は 64 KiB で、超過した場合は省略通知を stderr に加えてから末尾の内容を出します（`strata_cli/cli.py:2196-2214,2236-2248`）。

`--output json` または alias の `--json` を指定すると、quiet 判定より前に JSON 出力を選ぶため、JSON は stdout に出たままです（`strata_cli/cli.py:2232-2237`）。このコマンドの JSON は status 結果全体を `schema_version: 1` とともに出力します（`strata_cli/cli.py:1331-1373`）。

## 適用条件と副作用

このオプションは `strata runtime status` の parser に追加された one-shot フラグです。status は保存状態、host lease と owner host への照会を行います。ソース上、この status 呼び出しによるエンジン起動や停止は確認できません。`runtime status` の状態は最後の起動または明示的な verify の記録であり、エンジンの継続的な生存確認ではありません。再検証には `runtime verify` を使います（`docs/TERMINAL.md` の runtime 説明）。

## 出力とエラー

- 人間向け成功出力: `--quiet` により stdout から抑制されます。
- 人間向け失敗出力: `_runtime` が生成した status 行などの捕捉 stdout は stderr に移されます。status が `stale` や `failed` を返した場合、成功以外の終了コードを返します（`strata_cli/cli.py:1357-1373,2241-2248`）。
- JSON 出力: quiet でも stdout に保持されます。
- 不正な引数や `--profile` の欠落: argparse のエラー経路です。quiet は parser エラー表示を抑制しません（`strata_cli/cli.py:213-215,2223-2231`）。
- status 照会で制御先が利用できない場合など、例外は共通エラー処理から stderr と終了コードで報告されます。status 照会の RPC は接続不能時に code 3、応答待ち超過時に code 8、形式不正時に code 6 を設定します（`strata_control/runtime.py:402-440`）。

## 根拠

- `strata_cli/cli.py:213-215` — `runtime status` の parser と必須 `--profile`、既定 `--output human`。
- `strata_cli/cli.py:508-515` — `runtime_status` を含む one-shot parser 群への `--quiet` と `--json` の追加。
- `strata_cli/cli.py:1331-1373` — status 呼び出し、human/JSON 出力、戻り値。
- `strata_cli/cli.py:2196-2214,2232-2248` — quiet 捕捉、JSON の例外、失敗時の stderr 再出力。
- `strata_control/management.py:231-234`、`strata_control/runtime.py:444-455,1166-1172` — status の read-only 状態分岐と owner host への照会。
- `strata_control/runtime.py:402-440` — RPC の接続・待機・応答検証エラー。
- `docs/TERMINAL.md` — status が最後の起動/明示 verify 時点の記録であること、および quiet と JSON の一般説明。ソース挙動の根拠は上記コード位置に記載。

調査範囲は指定 commit の checkout 内の Python CLI / Control 実装と同 revision の `docs/TERMINAL.md` です。Release 配布バイナリや各 OS の実行結果は確認していません。
