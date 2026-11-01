# `--image-gpu-policy`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などの checkout wrapper からも引数を渡せる） |
| オプション | `--image-gpu-policy` |
| 別名 | なし |
| 値 | `auto`、`keep`、`shrink`、`unload` のいずれか。値は必須 |

## 役割

`--images qwen-image` で有効にする画像生成ジョブの間、テキスト用エンジンをどう扱うかを設定します。画像ジョブはサービスの GPU ターンを使い、設定された方針に応じてテキストエンジンを維持、VRAM 縮小、またはアンロードします（`serve/images.py:1-13,362-365`）。

この option は preview 扱いで、`setup.py --help` には表示されませんが parser は受理します（`setup.py:9096-9106`）。

## 使い方

checkout の通常の setup 経路で、画像生成を設定し、画像ジョブ中にテキストエンジンをアンロードする例です。

```sh
python setup.py --images qwen-image --image-gpu-policy unload --no-start
```

`--images` に `qwen-image` を渡した場合だけ `setup_images` が呼ばれ、この値が画像設定へ渡されます（`setup.py:5080-5104,10434-10435`）。画像モデルのダウンロードと画像 engine の build は別途発生します。`--no-start` はセットアップ後にモデルを起動しないための既存 option です（`setup.py:9142`）。

## 値と既定値

| 値 | 実行時の意味 |
| --- | --- |
| `auto` | 画像ジョブに必要な VRAM が空いていれば `keep`、空きが足りずエンジンが elastic なら `shrink`、それ以外は `unload`。UMA/APU では `keep` |
| `keep` | テキストエンジンをロードしたまま画像ジョブを実行 |
| `shrink` | エンジンの expert cache に VRAM を返す要求を出し、画像ジョブ後に元の reserve へ戻す |
| `unload` | エンジンを停止する。対応する単一リクエスト経路では会話をセッションファイルに保存し、後のロード時に復元する |

省略時、parser の値は `None` で、画像設定を作る際に `auto` が補われます（`setup.py:9105-9106,5101-5103`）。空文字列は選択肢にないため argparse が拒否します。値を省略した場合や許可外の値の場合は、argparse が usage とエラーを出して終了コード 2 で終了します（parser 定義 `setup.py:9105-9106`）。

## 実行時の動作

setup は選んだ値を run config の `images.gpu_policy` に保存します（`setup.py:5101-5103`、`tools/image/qimage.py:190-203`）。サービス起動時には `ImageGen` が値を再検証し、設定に値がなければ `auto` を使います。許可値以外なら `ValueError` になります（`serve/images.py:172-183`）。

各画像ジョブではサービスの FIFO ターンを取得し、並列生成中なら進行中のテキスト要求が終わるのを待ってから方針を解決します（`serve/images.py:362-400`）。`auto` は画像ジョブの必要 VRAM と空き VRAM を比べ、空き容量が測定できない場合も `keep` を選びます。elastic 判定は engine の `vram` 操作に加えて `vram_elastic` 情報または起動引数 `--vram-elastic` を見ます（`serve/images.py:327-353`）。

- `shrink` は `eng.vram(need)` を呼び、失敗しても警告ログを出して、確保できた VRAM のまま画像ジョブを続けます。終了後は最後に要求した reserve を戻そうとします。戻せなかった場合はログに記録し、`POST /v1/vram` で再試行できる旨を出します（`serve/images.py:407-417,437-443`）。
- `unload` は、engine が `session_file` に対応し batch 実行でない場合、会話を `images` の作業領域に一時 `.bin` ファイルとして保存してから engine を停止します。保存失敗時もログを出して停止を続け、vision engine があればそれも停止します。次の engine 起動時に会話を復元し、一時ファイルを削除します（`serve/images.py:418-433,454-467`）。
- unload 後の再ロードは既定で遅延し、次の必要時に行います。config に `reload: eager` があれば画像ジョブ後すぐロードを試みます。即時ロード失敗はログに記録され、次の要求で再試行します（`serve/images.py:177-179,444-451`）。setup が生成する画像 config には `reload` を指定していないため、通常は遅延です（`tools/image/qimage.py:190-203`）。

## 適用条件と副作用

- `--image-gpu-policy` 単独では効果がありません。画像生成が選ばれ、確認プロンプトでセットアップを続けた場合に設定へ反映されます。`--images no` または画像セットアップを断った場合には画像 config は生成されません（`setup.py:5080-5104`）。
- 通常の画像セットアップは画像 engine の build、モデルファイルのダウンロードと SHA-256 検証を行います。これは option 自体ではなく `--images qwen-image` に伴う処理です（`setup.py:5090-5102`）。
- 実行時の `keep` でも画像ジョブはサービスの GPU ターンを占有するため、画像処理とテキスト処理が同時にそのターンを使うわけではありません（`serve/images.py:1-13,362-400`）。
- 実行中エンジンがない場合、または `unload` を持たない場合は、指定値にかかわらず解決結果が `keep` になります（`serve/images.py:327-334`）。`auto` は UMA/APU でも `keep` を選びます（`serve/images.py:335-336`）。
- `auto` が選んだ `shrink` と明示的な `shrink` は同じ実行処理に入ります。elastic 未対応時の自動選択は `unload` ですが、明示 `shrink` は engine の VRAM 操作を試し、失敗しても画像ジョブを続けます（`serve/images.py:333-353,407-417`）。
- アンロードでは、会話の保存に失敗しても engine の停止を続けるため、保存できなかった会話状態は後から復元されません。batch 実行ではこのコードによる会話保存を行いません（`serve/images.py:418-433`）。

## 出力とエラー

setup 時に画像 config が作られると `image generation: <quant> on <backend>, GPU policy <value>` を表示します（`setup.py:5101-5103`）。実行中の shrink/unload の状況や失敗は `[strata]` のログへ出力されます（`serve/images.py:190-198,412-432,439-451`）。

parser は値の不足・不正値を拒否します。さらに、壊れた run config に許可外の `images.gpu_policy` が入っている場合は `ImageGen` の初期化が `ValueError` になります（`serve/images.py:172-183`）。これらの実行時エラーの最終的なプロセス終了コードは、この option の処理箇所だけからは確認できません。

## 根拠

- parser と preview/help 非表示の注記: `setup.py:9096-9106`。
- setup の値の既定化・画像 config への引き渡し: `setup.py:5080-5104,10434-10435`。
- run config での保存: `tools/image/qimage.py:190-203`。
- 実行時 validation、`auto` 解決、VRAM 制御、unload・会話復元: `serve/images.py:172-183,327-353,362-400,407-467`。
- `setup.py` parser へ渡す checkout 入口: `setup.sh`, `START-HERE.bat`（役割と委譲先は `docs/cli/000_cli_tools.md`）。

確認範囲は上記 commit の作業ツリーです。Release archive や各 GPU/backend 上での実動作はこの調査では確認していません。
