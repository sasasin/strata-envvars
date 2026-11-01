# `STRATA_TIMESKIP_PROMPT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。対象は Strata 所有ソース。外部ライブラリの環境変数動作は対象外。

## 役割

Time-skip が一回の revision attempt を起動するとき、利用者の依頼文を revision 子コマンドへ渡すための一時的な環境変数です。Strata CLI は `strata timeskip run --prompt ...` の値を `--revise-command` の子プロセス環境へ設定します。組み込み Python Harness helper (`integrations/harness/revise_once.py`) と、App Host のレガシー経路が使う Node helper (`apps/host/server/timeskip-revise.mjs`) がこの変数を読みます。CLI 自身はこの環境変数を読みません。通常の App Host 経路は fork runner に依頼文を直接渡すため、この変数を介しません（`strata_cli/cli.py:1570-1578`; `apps/host/server/index.mjs:1132-1152`; `apps/host/server/timeskip.mjs:426-436`）。

## 値と判定

この名前に固定の文字列値や数値形式はありません。値は依頼文として渡されます。読み取り先ごとの扱いは異なります。

| 経路 | 未設定・空文字 | 空白だけ | 非空文字列 |
|---|---|---|---|
| `integrations/harness/revise_once.py` | `os.environ.get(..., "")` の後 `.strip()` して空となる。stderr に `revise_once: STRATA_TIMESKIP_PROMPT is empty; nothing to ask for` を出し、終了コード 2 | `.strip()` 後に空となり、同じ失敗 | 前後の空白を除去した文字列を Harness の `session/prompt` 依頼に加える |
| `apps/host/server/timeskip-revise.mjs` | `?? ''` の結果が falsy となり、他の必須値とまとめて事前検査に失敗。stderr に `The revision step needs the Strata app to be running.`、終了コード 2 | truthy のため通過し、トリムせず内部 API に送る | 変換・trim せず内部 API に送る |

どちらの helper も環境値自体を数値変換したり、長さを制限したりしません。Node helper が送る依頼文は Host 側で `String(request).trim()` されます。Host のレガシー `/api/timeskip/start` 入力経路は、環境変数を設定する前に `body.prompt` を文字列化し、trim して最大 4000 文字に切り詰めます。直接 CLI を使う経路では、この Host 側の制限は適用されません（`apps/host/server/index.mjs:1132-1138,1220`; `apps/host/server/timeskip.mjs:132-145`）。

CLI の `--prompt` は必須引数ですが、CLI 側で空文字や空白のみを拒否する検査はありません。revision command が指定されると、CLI は親環境を複製した後で `STRATA_TIMESKIP_PROMPT` を `--prompt` の値に置き換えます。したがって、親環境に同名変数があっても CLI 引数が優先し、revision command を指定しない場合はこの環境変数を設定する subprocess も起動しません（`strata_cli/cli.py:353-365,1570-1578`）。

## 有効になる条件

- CLI 経路では `strata timeskip run` に `--revise-command` を指定し、attempt 数が 1 以上であることが必要です。コマンド未指定なら callback は revision を行わず `None` を返すため、変数の注入・読み取りはありません（`strata_cli/cli.py:1572-1578`; `strata_control/time_skip.py:442-449`）。
- 標準 Python helper を使う場合は、prompt が空白除去後に空でないことに加え、candidate directory、Harness CLI (`DSH_CLI` または既定パス)、Strata profile が存在する必要があります。これらの確認に失敗すると、prompt の空は終了コード 2、CLI/profile の欠落は終了コード 3 です（`integrations/harness/revise_once.py:84-100`）。
- App Host の `/api/timeskip/start` は `body.legacy !== true` なら fork runner を開始し、ここでは revision prompt を API 呼び出しへ直接渡すため `STRATA_TIMESKIP_PROMPT` は使われません。`body.legacy === true` の経路だけが既定 Node helper を revision command に設定します。`body.useAgent === false` の場合は revision command が null となり、標準 helper は呼ばれません（`apps/host/server/index.mjs:1132-1152`）。
- Node helper は prompt に加えて `STRATA_HOST_URL` と `STRATA_INTERNAL_SECRET` も空でないことを要求します。Host はこの二値をレガシー Time-skip 子プロセスへ注入します（`apps/host/server/index.mjs:1160-1165`; `apps/host/server/timeskip.mjs:446-455`; `apps/host/server/timeskip-revise.mjs:14-21`）。内部 API は認証後、candidate が Time-skip 状態ディレクトリ配下であること、利用可能なモデル選択があることを確認します。不一致などは HTTP 403、候補外は HTTP 400、モデル選択なしは HTTP 503 です（`apps/host/server/index.mjs:1194-1206`）。

OS、GPU backend、build macro による条件分岐はこの変数の読み取りにはありません。実際に revision を行うには上記の実行経路・コマンド・モデル等の条件を満たす必要があります。

## 実行時の詳細

CLI は `TimeSkipRun` に引数 `a.prompt` を渡し、各 attempt で作られた candidate directory を cwd として revision command を実行します。環境は `os.environ` から複製され、prompt と attempt 番号が上書き設定されます。Python helper は起動時に prompt を読み、前後空白を除去して Harness の `session/prompt` に `Goal:` として加えます。Node helper はモジュール評価時に prompt を定数へ一度読み、プロセス中に環境が変わっても再読込しません。いずれもリクエストごとの再読み込みはありません（`strata_cli/cli.py:1570-1578`; `integrations/harness/revise_once.py:84-86,129-136`; `apps/host/server/timeskip-revise.mjs:14-17,24-29`）。

Python helper は Harness の turn が正常完了したとき stdout に短い結果を出し終了コード 0 を返します。turn が未完了、期限超過、BridgeError、その他の例外は stderr と終了コード 1 になります（`integrations/harness/revise_once.py:138-173`）。Node helper は prompt 等の事前条件不足を終了コード 2、HTTP 応答失敗、error frame、result なし、通信例外を stderr と終了コード 1 で報告し、成功時は結果を stdout に出します（`apps/host/server/timeskip-revise.mjs:19-57`）。

CLI は revision command の非ゼロ終了を `the revision command failed (exit N): ...` として `TimeSkipError` にし、Time-skip run を `failed` に記録します。通常出力は `run <id> -> failed` と記録内容を表示し、終了コード 6 を返します。JSON 出力も失敗・中断状態で CLI error 終了コード 6 になります（`strata_cli/cli.py:1577-1588,1600-1602`; `strata_control/time_skip.py:486-493`）。

## 根拠

- 候補一覧に名前があることと実際の読み取り箇所を照合した。環境から値を読む本番コードは Python helper と Node helper の二箇所。`strata_cli/cli.py:1575` は CLI 引数値の子プロセス環境への設定であり、環境値の読み取りではない。その他の名前参照は CLI の help 文、コメント、実装状況文書、またはテスト fixture である（`000_envvers.md:1577`; `strata_cli/cli.py:362-365`; `docs/work/IMPLEMENTATION_STATUS.md:371-374`; `apps/host/tests/timeskip-real.test.mjs:61,145,157`）。
- CLI 引数から subprocess 環境への設定、非ゼロ終了処理: `strata_cli/cli.py:1570-1588`。
- Time-skip が各 attempt に revision callback を呼ぶ箇所と失敗 run の記録: `strata_control/time_skip.py:422-449,486-493`。
- Python helper の読み取り、空判定、Harness prompt、失敗出力: `integrations/harness/revise_once.py:84-100,129-173`。
- Host の通常経路とレガシー経路の分岐、レガシー helper 選択: `apps/host/server/index.mjs:1132-1152`。
- Node helper の起動時読み取り、必須値判定、内部 API への転送と結果処理: `apps/host/server/timeskip-revise.mjs:14-57`。
- Host の helper 起動環境への内部値注入と API 側処理: `apps/host/server/index.mjs:1160-1165,1194-1231`; `apps/host/server/timeskip.mjs:132-145,446-455`。
- `docs/DETAILS.md` に本変数の説明は見つからなかった。挙動の記述は上記 commit の実装に基づく。
