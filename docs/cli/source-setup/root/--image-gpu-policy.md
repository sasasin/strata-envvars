# `setup.py --image-gpu-policy`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（トップレベル） |
| オプション | `--image-gpu-policy` |
| 別名 | なし |
| 値 | `auto`、`keep`、`shrink`、`unload` のいずれか |

## 役割

画像生成をセットアップしたとき、画像ジョブ中にテキストモデルの GPU メモリをどう扱うかを実行設定の `images.gpu_policy` に記録します。この設定はセットアップ中の画像生成モデルのビルドやダウンロード方針ではなく、後の画像生成要求に対するテキストエンジンの扱いを決めます。parser はこの option を `--help` に表示しない設定です（`terminal/setup.py:11252-11266`）。

## 使い方

Strata checkout の `terminal/` で、画像生成を設定する例です。画像モデルのダウンロードと画像エンジンのビルドが行われ得るため、セットアップの確認に応答してください。

```bash
python3 setup.py --images qwen-image --image-gpu-policy auto --no-start
```

`--image-gpu-policy` だけを指定しても、画像設定を作成・更新しません。`setup_config.config_for()` は `--images` が与えられた場合だけ画像設定関数を呼び、未指定なら既存の `images` 設定を引き継ぎます（`terminal/strata_control/setup_config.py:574-576`）。`--images no` の場合は画像設定関数が `None` を返し、この option の値は設定されません（`terminal/setup.py:5898-5902`）。

## 値と既定値

| 値 | 実行時の方針 |
| --- | --- |
| `auto` | 画像ジョブに必要な空き VRAM が足りれば `keep`、足りずエンジンが可変 VRAM 対応なら `shrink`、それ以外は `unload`。統合メモリ環境では `keep`。 |
| `keep` | テキストエンジンを読み込んだまま待機させる。 |
| `shrink` | エンジンの expert cache を縮めて VRAM を空け、画像ジョブ後に設定済みの予約量へ戻す。 |
| `unload` | テキストエンジンを停止して VRAM を空ける。会話を保存できた場合は、次回エンジン起動時に復元する。 |

parser の `choices` は上記 4 値で、`default` は指定されていません（`terminal/setup.py:11265-11266`）。画像設定の生成時には、値が省略された場合に `auto` を渡します（`terminal/setup.py:5925-5928`）。実行時にも未設定または空の `gpu_policy` は `auto` として扱われます（`terminal/serve/images.py:361-365`）。

## 実行時の動作

`setup.py` は `--images qwen-image` が指定され、画像生成セットアップの確認を通った場合に、選択値（未指定なら `auto`）を `qimage.image_config()` に渡します。同関数はこれを `gpu_policy` として `images` 設定に格納します（`terminal/setup.py:5901-5929`、`terminal/tools/image/qimage.py:235-242`）。設定はモデルごとの run config に書かれ、既存設定が変わった場合は旧 config を `.bak` に保存してから書き込みます（`terminal/setup.py:7631-7669`）。

実行中は画像生成要求ごとにサービスの GPU turn 内で方針を解決し、画像ジョブの前後で必要な処理をします（`terminal/serve/images.py:607-645`）。画像ジョブの必要量は、設定が `need_mib` を持てばその値、なければモデルファイルのサイズ合計と画像寸法から算出した作業領域の見積もりです（`terminal/serve/images.py:342-355`）。

- `auto` は、統合メモリなら `keep`、空き VRAM が不明または見積もり以上なら `keep`、不足時はエンジンが `vram` 操作に対応し、稼働情報または起動引数から `--vram-elastic` が確認できれば `shrink`、それ以外は `unload` を選びます（`terminal/serve/images.py:571-598`）。
- `shrink` は `eng.vram(need)` を呼び、ジョブ後に `eng.vram(svc.vram_reserve)` で戻します。縮小または復元が失敗した場合はログを出します。縮小に失敗しても画像ジョブは利用可能な空き領域で続行し、復元に失敗した場合は `/v1/vram` で再試行できる旨を記録します（`terminal/serve/images.py:652-662,682-688`）。
- `unload` は、非 batch 実行で session 保存機能があれば会話を一時 session file に保存しようとし、その成否にかかわらずエンジンを unload します。vision エンジンにも unload があれば同様に停止します。保存できた会話は次の起動時に復元されます（`terminal/serve/images.py:663-678,699-710`）。セットアップ生成 config は `reload` を指定しないため、runtime の既定は `lazy` です。設定で `eager` が指定されている場合のみ、画像ジョブ後すぐの再起動を試みます（`terminal/tools/image/qimage.py:239-242`、`terminal/serve/images.py:366-377,682-696`）。

エンジンが稼働していないか `unload` 操作を持たない場合は、明示値も含めて解決結果を `keep` にします（`terminal/serve/images.py:571-579`）。したがってこの option は、画像生成を使わない実行や `--images` を指定しない setup では効果がありません。

## 適用条件と副作用

有効になるのは画像生成を設定し、その設定を使う画像生成要求の処理時です。セットアップ関数は確認後にモデル保存先を作成し、画像エンジンをビルドしてモデルファイルをダウンロード・SHA-256 検証します。これらは `--images qwen-image` のセットアップに伴う副作用であり、GPU policy の選択だけで発生する処理ではありません（`terminal/setup.py:5898-5929`）。

`unload` では一時 session file の作成を試みます。保存に失敗した場合も engine unload は続き、その一時ファイルの削除も試みます。保存済み会話は次回のエンジン起動時に復元され、復元に失敗した場合もエンジン自体は起動したまま、次の要求で prompt を読み直す旨を出力します（`terminal/serve/images.py:663-678,699-710`）。

## 出力とエラー

セットアップで画像設定が作られると、選択された quant・backend・policy を `[ok]` メッセージに表示します（`terminal/setup.py:5925-5929`）。choices 外の値は parser の choices 検査で拒否されます。画像 runtime でも設定値を再検査し、4 値以外なら `ValueError` を送出します（`terminal/setup.py:11265-11266`、`terminal/serve/images.py:361-365`）。

画像ジョブ中の VRAM 縮小・復元、会話保存・再ロードの失敗は `gen._say()` によるログ経路へ進み、前述の通り一部は失敗後も画像ジョブやエンジン起動を続けます（`terminal/serve/images.py:655-696`）。この調査ではセットアップや GPU を実行していないため、実機でのログ出力先・実際の VRAM 確保量・各 backend の成功可否は確認していません。

## 根拠

- `terminal/setup.py:11252-11266` — 画像生成関連 option 群の parser 登録、`--image-gpu-policy` の choices、help 非表示。
- `terminal/strata_control/setup_config.py:574-576` — `--images` 指定時だけ画像設定を作る条件。
- `terminal/setup.py:5898-5929` — `--images no` の扱い、確認、ビルド・ダウンロード経路、policy の `auto` fallback と成功表示。
- `terminal/tools/image/qimage.py:235-242` — run config の `gpu_policy` フィールド生成。
- `terminal/setup.py:7631-7669` — run config の引き継ぎ、バックアップ、書き込み。
- `terminal/serve/images.py:342-377,571-598,607-710` — 必要 VRAM の算出、policy 解決、GPU turn、縮小・unload・復元の実処理と失敗ログ。
