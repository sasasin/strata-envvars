# `GGML_VK_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata がこの名前を自身の環境から読み取って Vulkan デバイスを選ぶ処理は見つからない。Strata は画像生成サブプロセス `sd-cli` 用の環境を組み立てる際、画像設定の `backend` が `vulkan` で `gpu` が指定されていれば、この名前に `gpu` の値を設定して子プロセスへ渡す。また、サーバー起動元から継承した値や画像設定の `env` に書かれた値も、同じ子プロセス環境に渡す。ここで記述するのは Strata による環境の継承・設定・転送であり、受け取った `sd-cli` や Vulkan ライブラリ、GPU ドライバーでの解釈ではない。

この経路は設定済みの画像生成機能（`POST /v1/images/generations`）が `sd-cli` を起動するときに使われる。テキストエンジンの起動環境を作る `child_env()` とは別の経路である。

## 値と判定

Strata は `GGML_VK_VISIBLE_DEVICES` の値を parse、検証、正規化しない。変数名は backend ごとの対応表にあり、環境変数への代入は画像設定から作る。

| 入力・条件 | `sd-cli` 用環境での Strata の処理 |
|---|---|
| `gpu` が未指定（`None`） | backend にかかわらず GPU 用の代入をしない。親環境に同名変数があれば、その値を引き継ぐ。 |
| `gpu` が指定済み、`backend` が文字列 `vulkan` | `gpu` が list/tuple なら各要素を `str()` 化し、前後空白を除去し、空要素を落としてカンマ結合する。スカラーなら `str(gpu)` をそのまま設定する（スカラーの空白除去はしない）。 |
| `gpu` が指定済み、`backend` が `cuda` / `hip` | 対応する別名 `CUDA_VISIBLE_DEVICES` / `HIP_VISIBLE_DEVICES` を設定する。この分岐では対象変数を設定しないため、継承値は残る。 |
| `gpu` が指定済み、その他の `backend` | GPU 用の代入をしない。親環境に同名変数があれば、その値を引き継ぐ。 |
| 画像設定の `env` に同名キーがある | 最後に `str()` 化した設定値で上書きする。`gpu` による代入があっても同じ。 |

したがって、対象変数についての優先順位は、親プロセスの環境値を初期値とし、`backend == "vulkan"` かつ `gpu is not None` の設定で置換し、最後に画像設定の `env` で再置換する順である。空文字や不正に見える文字列でも Strata は拒否せず、そのまま、または上記の `gpu` 変換結果として転送する。数値範囲やデバイス番号の有効性を Strata が検査するコードはない。

## 有効になる条件

- サーバー設定に `images` セクションがあり、画像生成用 `ImageGen` が初期化されていること。画像生成が設定されていなければ endpoint は HTTP 404 を返し、`sd-cli` は起動しない。
- 画像ジョブの実行時に `sd-cli` を起動すること。Strata は `image_env()` の返す環境をその起動に渡す。
- Strata が値を設定するのは画像設定の `backend` が厳密に `vulkan` と一致し、かつ `gpu` が `None` でない場合だけ。OS や Strata の GPU build macro による追加条件はこの代入コードにはない。
- 画像設定 `env` は GPU 選択の代入より後に適用されるため、同じキーがあれば最終値になる。CLI 引数からこの変数を直接上書きする処理は、この起動経路では確認できない。

## 実行時の詳細

`image_env()` は呼び出しごとに `os.environ`（または任意の `base`）を辞書コピーし、設定から必要なライブラリ検索パスや GPU 用環境変数を加え、最後に `cfg["env"]` を反映する。値を static cache する処理はない。本番では各画像ジョブの `sd-cli` 起動時に `image_env(self.cfg)` が評価されるため、その時点のサーバープロセス環境がベースになる。

対象変数専用の Strata ログや警告はない。`sd-cli` 起動時の `OSError` は `ImageJobFailed` となり、画像 API は HTTP 500 `image_generation_failed` を返す。起動後に `sd-cli` が非ゼロ終了する、または画像を書かない場合、Strata はログ末尾最大 12 行と失敗理由を `[strata] image job failed: ...` として出し、同じく HTTP 500 を返す。これらは一般の画像ジョブ失敗経路であり、対象変数の値が原因であることを Strata が識別するものではない。

## 根拠

- `serve/images.py:131-150` — 親環境の複製、backend と `gpu` による変数名選択・値変換、`cfg.env` による最終上書き。
- `serve/images.py:221-239` — 画像ジョブごとの `image_env(self.cfg)` 評価と `sd-cli` 子プロセスへの `env` 引き渡し、および起動失敗の変換。
- `serve/images.py:263-273` — 子プロセス終了・出力ファイルの確認、失敗時のログ末尾出力。
- `serve/server.py:7603-7628` — `/v1/images/generations` の未設定時 404、画像ジョブ失敗時 500。
- `serve/server.py:9191-9194` — Strata テキストエンジン用に `child_env()` から環境を作る別経路。
- `serve/server.py:9331-9345` — 設定の `images` セクションから画像生成機能を初期化。
