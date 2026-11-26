# `STRATA_ONBOARDING_GPUS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

これは Strata の通常アプリや engine の設定ではなく、UI の初回起動画面を表示するスクリーンショット用 fixture 専用の入力である。設定されると fixture の模擬ハードウェア GPU 配列を置き換え、さらにモデルをロード済みとしていた状態を解除して、GPU ロールの推奨プレビューを表示できる状態にする。対象名の参照は `app/host/tests/fixtures/onboarding-ui-host.mjs` の2箇所だけで、engine・production server・通常アプリの読み取り箇所は見つからなかった（同ファイル:11,67）。fixture 自身も「Screenshot-only first-launch fixture」と明記している（同ファイル:1）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `onboarding-ui-host.mjs` fixture | 初期値の模擬 GPU 1台（scenario が `multi-gpu` なら2台）を使う。`STRATA_ONBOARDING_START=ready` なら生成された ready 状態を保つ | 空文字列以外なら `JSON.parse` の結果を `native.hardware.gpus` にそのまま代入し、`instances` を空、`defaultId` を null にする。JSON 配列を期待するコードだが、配列型・要素・範囲の検証はない | 空文字列は JavaScript の falsy 判定で未設定と同じ扱い。JSON として不正な非空文字列は parse 例外になる |

環境変数の値全体を JSON として parse する。`[]` や `[{"index":0,"name":"GPU","vram_gb":8}]` は parse できる配列の例で、`[]` なら fixture は GPU 0 台を返す。`0`、`1`、`true`、`false`、`null`、`{}` も JSON として parse されて代入されるが、配列型の検査はないため、後続の `/api/hardware` 応答が `gpus.map(...)` を呼ぶと例外になる。`0anything` や空でない不正 JSON は parse 例外になる。前後の空白は JSON parser が受理する範囲で parse される。配列要素の構造・値域も検証されず、想定プロパティを持たない要素は GPU 情報や VRAM 合計が不完全になる（同ファイル:11,142-148,154）。

初期 GPU 配列は index 0 の NVIDIA RTX 4090 である。`STRATA_ONBOARDING_SCENARIO=multi-gpu` の場合だけ index 1 の RTX 3090 が先に追加されるが、この変数が truthy なら配列全体を置き換えるため、scenario で作った配列よりこちらが優先される（同ファイル:9-11）。CLI 引数や他の設定値との優先順位はない。

## 有効になる条件

- `app/host/tests/fixtures/onboarding-ui-host.mjs` を実行する場合だけ有効。`preview-ui.mjs` と `language-shots.mjs` は fixture を子プロセスとして起動し、親プロセス環境を引き継ぐ（`app/host/scripts/preview-ui.mjs:13,24`、`app/host/scripts/language-shots.mjs:30,40`）。
- 値が空でないと GPU 配列を差し替える。さらに同じ環境変数の truthy 判定により `native.instances=[]`、`native.defaultId=null` となるため、`STRATA_ONBOARDING_START=ready` で準備済みモデルを作ってもロード済みインスタンスを残さない（fixture:51-67）。
- 通常の Strata 実行経路への適用、OS・backend・GPU 世代・build macro による分岐はない。全リポジトリの名前完全一致検索では上記 fixture 以外の参照は見つからなかった。

## 実行時の詳細

fixture のモジュール初期化時に、9行目で模擬 GPU 配列を作り、11行目で環境値を読み直して必要なら上書きする。準備済み・ready 状態の生成後、67行目でも同じ環境変数を読み、GPU 配列を差し替えた場合には `instances` と `defaultId` を再度クリアする。いずれもサーバー起動前の同期的な初期化であり、起動後に環境を変更してもこの状態更新は再実行されない（fixture:7-11,51-67,155-157）。

有効な JSON 文字列なら値を `native.hardware.gpus` に設定し、fixture の `/api/hardware` 応答で各要素を `{index,id,vendor,name,vramGb,backend,unified}` の GPU 情報へ写し替える。また配列要素の `vram_gb` 合計を `usableVramGb` に設定し、accelerator label を `Fixture GPUs` とする。これは fixture が返す模擬データの変化であり、実機検出、GPU 選択、engine 起動、推論の制御ではない（fixture:142-148）。

無効 JSON はトップレベル初期化中の `JSON.parse` で失敗する。サーバーの `listen` はファイル末尾にあるため、その場合は fixture の HTTP サーバー起動まで到達しない（fixture:11,155-157）。ルートハンドラ内の例外は HTTP 400 と例外メッセージの JSON 応答になるが、起動時 parse 例外はこの handler の `try/catch` の外にある（fixture:95-97,142-157）。

## ログと測定値

fixture が正常起動したときは `Disposable onboarding screenshots: http://127.0.0.1:${port}` を console に出す。`${port}` は `STRATA_ONBOARDING_PORT` の数値変換結果で、既定は `5271`（fixture:156-157）。対象変数自体の有効・無効を示す専用ログはない。測定値の記載はない。

## 根拠

- `app/host/tests/fixtures/onboarding-ui-host.mjs:1,7-11` — fixture の用途、初期模擬 GPU、scenario 追加、対象変数の判定と JSON parse。
- `app/host/tests/fixtures/onboarding-ui-host.mjs:51-67` — start 状態の生成と、対象変数が設定されている場合の loaded instance 解除。
- `app/host/tests/fixtures/onboarding-ui-host.mjs:142-157` — hardware API への GPU 値の反映、要求時の例外応答、起動ログ。
- `app/host/scripts/preview-ui.mjs:13,24`、`app/host/scripts/language-shots.mjs:30,40` — fixture の起動と環境継承。
