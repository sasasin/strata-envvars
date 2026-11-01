# `DS4_ENC_EACH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリと Metal driver の動作は対象外。

## 役割

Metal の DeepSeek DS4 実行経路で、遅延実行中の各 dispatch の後に compute encoder を終了し、同じ command buffer 内に次の encoder を作ります。未設定時でも `DS4_TIMELINE` が有効なら同じ動作を選びます。これは encoder の区切り方を変える診断用の設定で、command buffer の commit や GPU 完了待ちを各 dispatch ごとに行う設定ではありません。

## 値と判定

| `DS4_ENC_EACH` | 判定 |
|---|---|
| 未設定 | `DS4_TIMELINE` が有効でなければ無効。有効なら encoder を dispatch ごとに区切る |
| 空文字を含む任意の設定値 | 有効。文字列の内容や数値への変換は行わず、`getenv()` が null でないかだけを判定 |

判定結果は関数内の `static const bool` に保存されます。`Context::run()` の該当経路で最初にこの判定へ到達した時点の値が、そのプロセス内で使われ続けます。後から環境を変更しても再評価されません。

## 有効になる条件

- macOS の Metal `strata_ds4` 実行ファイルに組み込まれる `STRATA_DS4_RUNTIME` 経路が対象です。Metal runtime の共通ファイルでも、この macro が有効な DS4 向け object として `strata_ds4` に組み込まれます。
- `Context::run()` に渡された dispatch が1件、`reps == 1`、`barrier_between == false` の遅延実行経路に入った場合にのみ、この環境変数の判定と処理が実行されます。それ以外の `run()` 経路と `run_graph()` にはこの分岐がありません。
- `DS4_TIMELINE` が設定されている場合、Context 初期化時に timeline が有効化されます。ただし timestamp counter set または counter sample buffer が使えず `g_tl.on` が解除された場合、`DS4_ENC_EACH` も未設定なら encoder 区切りは選択されません。`DS4_ENC_EACH` 自体が設定されていれば timeline の状態にかかわらず選択されます。

## 実行時の詳細

遅延経路では、dispatch を encoder に encode し、通常は buffer scope の memory barrier を追加した後、`DS4_ENC_EACH`（または `g_tl.on`）が真なら現在の encoder に `endEncoding` を呼び、同じ command buffer に次の encoder を作ります。新 encoder の dispatch type は `DS4_CONCURRENT` の設定有無から決まります。command buffer はこの分岐の直後には commit されず、後続 dispatch を含み得ます。

この変数専用のログ、警告、終了・失敗処理はありません。timeline を別途有効にした場合には、Metal runtime が counter 対応状況に応じて `mtl: DS4_TIMELINE: no timestamp counter set` または `mtl: DS4_TIMELINE: no counter sample buffer` を stderr に出して記録を無効化する経路があります。これは `DS4_ENC_EACH` の値を検査した結果ではありません。

## 根拠

- 値判定、適用される `Context::run()` 条件、dispatch ごとの encoder 終了・再作成: `metal/src/mtl_rt.mm:902-960`（特に `908-910`, `936-946`）。
- timeline の初期化と `DS4_ENC_EACH` との OR 条件に使われる `g_tl.on`: `metal/src/mtl_rt.mm:78-93,95-153,292-301,941-945`。
- DS4 専用 macro 付き runtime object のビルドと `strata_ds4` への組み込み: `metal/CMakeLists.txt:151-165`。DS4 runtime が `strata_ds4` のみにコンパイルされる説明: `docs/DEEPSEEK_MAC.md:91-95`。
- 候補一覧にも `DS4_ENC_EACH` がある: 調査側 `docs/envvars/000_envvers.md:174`。動作の根拠には使用していません。
