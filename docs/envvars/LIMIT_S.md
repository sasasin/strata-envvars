# `LIMIT_S`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`LIMIT_S` は `apps/host/scripts/load-pictures-e2e.mjs` 専用の実行時間上限（秒）です。この Node.js スクリプトは、起動中の Host の Models ページでモデルの Load 操作を行い、ジョブ状態をポーリングしてタイムラインやスクリーンショットを保存する E2E 診断用ハーネスです。Strata の通常の CLI、Host サーバー、モデル実行の設定値としては参照されていません。実際の読み取りは同スクリプトの `process.env.LIMIT_S` 一箇所です（`apps/host/scripts/load-pictures-e2e.mjs:1-12,19-25`）。

## 値と判定

スクリプトのモジュール評価時に `Number(process.env.LIMIT_S ?? 900) * 1000` として一度読み、ミリ秒へ変換します（`apps/host/scripts/load-pictures-e2e.mjs:23`）。`??` を使うため未設定の場合だけ既定値 `900` 秒になり、明示した空文字は既定値に置き換わらず `Number("")` の結果である `0` 秒になります。

| 環境値 | `LIMIT` の結果 | 処理 |
|---|---:|---|
| 未設定 | 900,000 ms | 最大 900 秒のポーリング上限 |
| 数値として解釈できる文字列 | `Number(value) * 1000` | その秒数を上限にする |
| 空文字、または空白だけ | 0 ms | ポーリング本体に入らず、終了後処理へ進む |
| `0` または負数 | 0 または負のミリ秒 | ポーリング本体に入らず、終了後処理へ進む |
| 数値にできない文字列 | `NaN` | 比較式が成立せず、ポーリング本体に入らない |
| `Infinity` | `Infinity` | 時間上限ではループを止めない。ジョブが終了状態になるまで続く |

JavaScript の `Number` 変換なので、整数だけに限定する検査、正の値かどうかの検査、clamp、エラー時の fallback はありません。数値表記の可否は `Number` の変換規則に従い、例えば `12abc` は `NaN` になります。CLI 引数や別の設定ファイルによる上書きもありません（`apps/host/scripts/load-pictures-e2e.mjs:19-25`）。

## 有効になる条件

- この E2E スクリプトを Node.js で起動した場合にだけ読み取られます。通常の Host 起動や Strata CLI の経路でこの値を読む箇所は、リポジトリ全体の `LIMIT_S` 検索では確認できません。
- `HOST_URL` が未設定または空文字なら、スクリプトは `HOST_URL is required` を stderr に出して終了コード 2 で終了します。この検査は `LIMIT_S` の値を使うポーリングより前です（`apps/host/scripts/load-pictures-e2e.mjs:19-20,48-62`）。
- スクリプトは Models ページ上のボタンが有効になるまで別の固定上限で待機し、ボタンを押してから `LIMIT_S` によるジョブ監視ループを開始します。そのため `LIMIT_S` はページ準備待ちの上限を変更しません（`apps/host/scripts/load-pictures-e2e.mjs:51-62`）。
- 値は起動時に定数へ格納されます。実行中に環境を書き換えても再評価されません（`apps/host/scripts/load-pictures-e2e.mjs:23`）。

## 実行時の詳細

Load ボタンを押した時点で経過時間の計測を始め、`Date.now() - started < LIMIT` の間、ページ表示と `/api/native` の最新ジョブ状態を確認します。状態が変化したときタイムラインへ記録し、ジョブが今回の実行で開始され、`running` 以外の状態になればループを抜けます。各反復の後には 500 ms 待ちます（`apps/host/scripts/load-pictures-e2e.mjs:59-76`）。

時間上限に達した場合は `ended` が `null` のまま後処理に進み、1.5 秒待ってスクリーンショットを撮り、`<OUT>/timeline.json` と標準出力へ結果を記録します。`ended === 'done'` のときだけ終了コード 0 で、それ以外（タイムアウトを含む）は終了コード 1 です。例外経路ではエラーメッセージを stderr と `<OUT>/error.txt` に書き、終了コード 2 で終了します（`apps/host/scripts/load-pictures-e2e.mjs:77-87`）。

## 根拠

- 候補名の全参照検索では、実コード上の読み取りは `apps/host/scripts/load-pictures-e2e.mjs:23` の一箇所でした。コメントには既定値の説明があります（同 `:8-12`）。
- スクリプトの用途と起動例: `apps/host/scripts/load-pictures-e2e.mjs:1-12`。
- 値の取得と数値変換: `apps/host/scripts/load-pictures-e2e.mjs:19-25`。
- ページ準備、Load 操作、監視ループ: `apps/host/scripts/load-pictures-e2e.mjs:48-76`。
- タイムアウト後の出力、正常・異常終了経路: `apps/host/scripts/load-pictures-e2e.mjs:77-87`。

`LIMIT_S` に関する記述は `docs/DETAILS.md` では見つかりませんでした。測定値や通常の実行時機能を示す資料も確認できていません。
