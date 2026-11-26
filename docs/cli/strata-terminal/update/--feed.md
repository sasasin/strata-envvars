# `strata update --feed`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--feed` |
| 別名 | なし |
| 値 | 署名付き update feed の URL またはフォルダー／ファイルパス。parser に型・形式の検証や既定値はない。 |

## 役割

更新情報を読む feed の場所を指定する。指定した feed はエンジンや Control の更新対象を選ぶ情報源となり、feed 本体と署名ファイルを読み取って署名・内容を検証した後に更新処理へ渡される。`strata update --check` でも同じ場所から feed を読み、更新計画を表示する。

## 使い方

```sh
# HTTPS 上の feed ファイルを読み、更新内容だけ確認する（feed 以外はダウンロードしない）
strata update --feed https://updates.example.org/strata-feed.json --check

# オフラインで用意した feed のフォルダーから通常の更新を行う
strata update --feed ./update-feed
```

## 値と既定値

- `--feed` は値を1つ取る。`argparse` 登録に `type`、`choices`、明示的な `metavar`、または既定値はなく、省略時は `None`。同じオプションを複数回書いた場合の独自処理はなく、標準の `argparse` が後に指定された値を引数値にする（`terminal/strata_cli/update_cmd.py:47-49`）。
- feed の場所は次の順で選ばれる。
  1. 空でない `--feed` の値。
  2. 空でない `STRATA_UPDATE_FEED`。
  3. update state に記録された HTTPS feed。以前の記録が共通 feed の URL の場合は、プラットフォームに応じた feed 名へ置き換える。
  4. プロジェクトの既定 feed。Linux ARM64 では `strata-feed-linux-aarch64.json`、それ以外では `strata-feed.json`。

  この順序は `terminal/strata_cli/update_cmd.py:33-45,142-158` による。`STRATA_UPDATE_FEED` の独立した調査文書は現行 `docs/envvars/` に見当たらないため、詳細仕様へのリンクは付けていない。
- 明示値が URL の場合、`https`、loopback 宛の `http`、または `file` が feed reader で扱われる。`http` は loopback 以外では拒否される（`STRATA_UPDATE_ALLOW_HTTP=1` の場合を除く）。対応する形式の外側にある値の細かな検証は parser ではなく取得側で行われる（`terminal/strata_control/transfer.py:7-9,154-175`）。
- URL が `.json` で終わらない場合、URL をフォルダー相当として扱い、末尾にプラットフォーム別 feed 名を加える。ローカルのフォルダーでも同名を探し、存在しない場合は `strata-feed.json` があればそちらを使う。`.json` ファイルを直接指定した場合はそのパスを使う（`terminal/strata_control/feed.py:680-688,697-705`）。
- ローカルパスや loopback URL は次回起動時の記憶済み feed として再利用されず、再度指定しない場合は既定 feed に戻る。記憶対象は HTTPS URL のみ（`terminal/strata_cli/update_cmd.py:148-158`）。

## 実行時の動作

`strata update` と `strata components update` は共通の parser 登録関数を通るため、どちらのコマンドでも同じ `--feed` を受け付ける。ここでは索引で指定された `strata update` の scope を記録する（`terminal/strata_cli/update_cmd.py:47-49,59-79`）。通常の `strata update` 経路は feed の場所を決めて update context に設定し、`--check` なら `updater.check`、それ以外ならモデルの稼働状態を扱う更新処理に渡す（`terminal/strata_cli/update_cmd.py:355-377`）。

feed reader は feed 本体と隣接する署名ファイルを取得し、信頼鍵による署名検証、feed の解析、channel・有効期限・既受理 sequence との照合を行う。検証に通った feed の sequence、鍵 ID、source などは state に記録される（`terminal/strata_control/feed.py:650-677,691-717`; `terminal/strata_control/updater.py:451-470`）。`--check` は feed を取得し、結果と最終確認情報を state に保存する一方、feed が示すコンポーネント本体はダウンロードしない（`terminal/strata_control/updater.py:778-789`）。通常更新では feed の項目に従って更新処理が進む。`--feed` 自体はファイルを書き込まず、取得した feed と更新処理がネットワーク・ローカルファイルに作用する。

## 適用条件と副作用

- update は明示的な取得操作であり、`STRATA_NO_ACQUIRE` によって取得が禁止されたプロセスでは拒否される（`terminal/strata_cli/update_cmd.py:355-358,387-388`）。
- 指定 feed の署名が信頼鍵で検証できない、feed が不正・期限切れ、channel が不一致、または sequence が記録済みの値より古い場合は受理されない（`terminal/strata_control/feed.py:650-677`）。
- feed の読み取りに失敗した場合、ネットワーク到達不能および転送エラーは終了コード `6`、署名・feed 検証エラーは通常 `5` で失敗処理へ送られる（`terminal/strata_control/feed.py:50-60,691-717`; `terminal/strata_cli/update_cmd.py:378-388`）。
- 成功した feed の取得では、検証後に feed 情報を update state に保存する。`--check` も `last_check` 情報を書き込む（`terminal/strata_control/updater.py:451-470,778-789`）。

## 出力とエラー

- 通常の更新では human 出力に選択した source が `Strata update (<source>)` として表示される。`--check` は feed の sequence、channel、署名鍵 ID と、コンポーネントごとの見込みを表示する（`terminal/strata_cli/update_cmd.py:217-253,361-372`）。
- `--output json` または `jsonl` の場合、machine 出力を使う。feed エラーは JSON の `ok: false` と `error.code` / `error.message`（`jsonl` ではなく通常 JSON）として標準出力へ出力される。それ以外は `strata: <message>` を標準エラーへ出し、対応する終了コードを返す（`terminal/strata_cli/update_cmd.py:117-139,309-316,378-388`）。
- feed host が応答しない場合は終了コード `6`。ネットワーク以外の転送失敗も `6` に変換される（`terminal/strata_control/feed.py:706-717`）。信頼鍵がない、署名が不正、期限切れ、古い sequence などの検証失敗は既定で終了コード `5`（`terminal/strata_control/feed.py:50-55,650-677`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:33-49,59-79` — 既定 feed と `--feed` の parser、対象コマンド範囲。
- `terminal/strata_cli/update_cmd.py:142-158,355-377` — source の優先順位、記憶条件、通常更新／check への引き渡し。
- `terminal/strata_control/transfer.py:7-9,154-185` — source の種別、URL scheme とローカルパスの扱い。
- `terminal/strata_control/feed.py:650-677,680-717` — 署名・feed validation と feed ファイル／署名の取得。
- `terminal/strata_control/updater.py:451-470,778-789` — feed state の更新と `--check` の state 副作用。
