# `STRATA_NO_BUNDLED_ENGINE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

インストーラーに同梱された engine package を、ホスト起動時にユーザーの components store へコピー（または同じ package の破損コピーを修復）する処理を止めます。Control が見つかったホストでのみ判定されます。既に store にある engine を無効化・削除する設定ではなく、engine の選択やモデル起動を直接切り替える設定でもありません。

## 値と判定

`apps/host/server/index.mjs` は `process.env.STRATA_NO_BUNDLED_ENGINE` を文字列 parse せず、JavaScript の truthiness で判定します（146, 152行）。

| 状態 | 同梱 engine 処理 |
|---|---|
| 未設定 | 有効（ただし Control が存在する場合） |
| 空文字 (`STRATA_NO_BUNDLED_ENGINE=`) | 有効（空文字は falsy） |
| 空でない文字列 | 無効化される。`1`、`0`、`false` などの文字列はいずれも truthy |
| Control がない | 環境変数の式は短絡評価され、同梱 engine 処理は行われない |

この変数を読む箇所は `index.mjs` の146行と152行です。両方ともモジュール初期化時の分岐に使われます。起動後に `process.env` を変更しても、開始済みの Promise や `bundledEngineSettled` は再評価されません。CLI 引数による上書き経路はありません。

## 有効になる条件

- `findControl()` が Control を検出して `control` を作成できることが必要です。Control は `STRATA_CONTROL_DIR`、host 隣の `control`、または components 内の更新済み Control から検出されます。どれも見つからない source checkout では `control` が `null` になり、変数は実質的に参照されません（`apps/host/server/control-runtime.mjs:52-75,172-174`）。
- Control がある場合、未設定または空文字なら `installBundledEngine()` を呼び、空でない値なら呼びません（`apps/host/server/index.mjs:145-153`）。OS/backend による変数値の判定差はありません。
- 同梱 bundle の場所は別変数 `STRATA_ENGINE_BUNDLE_DIR` が truthy ならその値、それ以外は host からの既定相対パスです（`apps/host/server/index.mjs:146-149`）。この変数はその場所を選びません。
- package の展開が行われる場合も、bundle の存在、manifest、OS/backend、GPU backend、NVIDIA driver、components store 内の同版 engine などにより、結果は `none`、`wrong-make`、`kept`、`installed`、`repaired`、`refused` になり得ます（`apps/host/server/bundled-engine.mjs:168-232,233-267`）。本変数はそれらの適合判定より前に処理全体をスキップします。

## 実行時の詳細

起動時に変数が truthy なら、`bundledEngine` は `{ action: 'none' }` で解決する Promise になります。インストールまたは修復は呼び出されず、`bundledEngineSettled` は初期値 `true` になります。したがって `/api/control/status` の `engineSetup` は false となり、同梱 engine の展開中を示す状態にはなりません（`apps/host/server/index.mjs:146-153,1291-1303`）。この設定は Control による既存 engine の検出を止めません。同 API は引き続き `control.engine()` の結果を返します（同1292-1300行）。

無効化されていない場合、host は `engine-bundle` 内の manifest を確認し、対象 package を components の `engine` 配下へコピーします。同版以上の完全な engine が既にあれば保持し、同じ package の不完全なコピーなら修復します。成功時は `bundled engine <名前>: installed|repaired` 等を `console.log` に出し、manifest 不一致やコピー失敗は `refused` の理由をログに出します（`apps/host/server/bundled-engine.mjs:168-267`）。

`cleanupAfterInstall()` は変数の値にかかわらず呼ばれますが、Promise の結果が `installed`、`kept`、`repaired` の場合だけ bundle の削除確認へ進みます。無効化時の `{ action: 'none' }` では確認も削除も行いません（`apps/host/server/index.mjs:149-153`; `apps/host/server/bundled-engine.mjs:314-320`）。

モデル起動や既存 engine の実行可否をこの変数が決める処理は確認できません。したがって、同梱 engine のない状態で有効化した場合に engine が利用可能かどうかは、Control が検出する engine や別途インストールされた components によります。ホスト起動ログは通常の inference 状態を表示し、同梱処理が非同期中なら `unpacking the bundled engine… (about a minute the first time)` と表示します（`apps/host/server/index.mjs:278-284`; `apps/host/server/inference.mjs:527-536`）。

## 根拠

- 読み取りと起動時の分岐、bundle 既定パス、settled 状態: `apps/host/server/index.mjs:145-153`
- Control 検出条件と Control がない場合の `null`: `apps/host/server/control-runtime.mjs:52-75,172-174`
- package の適合確認、コピー・修復・拒否とログ: `apps/host/server/bundled-engine.mjs:168-267`
- bundle cleanup の実行条件: `apps/host/server/bundled-engine.mjs:314-320`
- 起動表示と Control status API: `apps/host/server/index.mjs:278-284,1291-1303`; `apps/host/server/inference.mjs:527-536`
- 同梱テストではホスト子プロセスの環境に `STRATA_NO_BUNDLED_ENGINE: '1'` を設定しています。これはテスト設定であり、環境変数の判定・挙動の根拠は本番コードです（`apps/host/tests/app-ui.test.mjs:97-103`）。
