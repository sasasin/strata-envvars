# `STRATA_INKLING_IMAGE_MAX_MP`

調査対象: Strata `main` の HEAD `c234774038d1c9249cb33637d27b895d47b39786`（`2026-11-26` 時点）。

## 役割

Inkling-2-Mini を動かす Strata サーバーで、エンジンに渡す前の画像の最大画素数をメガピクセル単位で指定する。閾値より大きい画像を同じ縦横比で縮小し、閾値以下なら元データを渡す。設定はサーバー起動時に画素数へ変換され、画像付きリクエストの準備時に適用される。環境変数は run config の `inkling_image_max_mp` が未設定または空文字の場合に使われ、非空の config 値が優先する。`image_cap_pixels` と `cap_picture` が実装箇所。`terminal/serve/inkling_kind.py:322-372`、適用箇所 `terminal/serve/server.py:9702-9710,5683-5701`。

## 値と判定

環境値は Python の `environ.get(...)` で取得し、`or ""` の後に `.strip()` を適用する。未設定、空文字、空白だけの値は未設定扱い。残りは `float(raw)` で文字列全体を数値に変換する（数値の後ろに文字が付く値は不正）。bool、NaN、負値、1,000,000 を超える値は拒否され、範囲内の数値は `int(mp * 1_000_000)` により画素数へ変換される。`terminal/serve/inkling_kind.py:322-337`。

| 条件 | unset（環境値も config も未設定） | 有効になる値の例 | 無効になる値の例 |
| --- | --- | --- | --- |
| backend が `hip`、`sycl`、`metal` | 0（上限なし） | `0`（上限なし）、`0.8`、`2.5` | `true`、`0anything`、`-1`、`1000000.1` |
| 上記以外（`cuda`、`cpu`、backend 名なしを含む） | 800,000 px（0.8 MP） | `0`（上限なし）、`0.8`、`2.5` | `true`、`0anything`、`-1`、`1000000.1` |

GPU picture backend の判定集合は `("hip", "sycl", "metal")`。任意の backend でも明示した 0 以上 1,000,000 以下の値は使われ、上限画素数は `int(MP × 1,000,000)` になるため、小数の画素端数は切り捨てられる。環境値の前後の空白は除去される。大文字小文字を使う真偽値判定はなく、`true` / `false` は数値でないため不正。`terminal/serve/inkling_kind.py:318-337`。

非空の run config 値が環境値より優先する。config の値が `None` または `""` なら環境値に進み、環境値も空または空白だけなら backend 別の既定値を使う。無効な非空値に対する fallback や clamp はなく、起動処理が `[strata] config "inkling_image_max_mp" must be a number of megapixels, 0 for no cap, not ...` を出して終了する。`terminal/serve/inkling_kind.py:326-337`、`terminal/serve/server.py:9702-9707`。

## 有効になる条件

- `svc.inkling` が真のときだけ設定が読み込まれ、画素数がサービスに設定される。Strata engine の Inkling-2-Mini 経路が対象。その他のモデルや `--engine` が Strata 以外の経路ではこの設定処理に入らない。`terminal/serve/server.py:9683-9707`。
- この変数は backend 既定値を変える。HIP / SYCL / Metal の画像読取経路でも、正の上限を明示すれば縮小処理が有効になる。未設定時はこれらの backend は上限なし。`terminal/serve/inkling_kind.py:318-337`。
- 上限が 0 の場合、または画像画素数が上限以下の場合は縮小しない。Pillow が利用できない場合、または画像を Pillow で開く・処理する際に例外が起きた場合も元データをそのまま渡す。`terminal/serve/inkling_kind.py:340-369`。
- 画像を受け付けて処理するには、エンジン情報で `images` が `1` であることが必要。満たさない場合は画像処理前に `NO_IMAGES_REPLY` の `ValueError` となる。`terminal/serve/server.py:5683-5686`。

## 実行時の詳細

サーバーの config を起動時に読み込んだ後、Inkling サービスの初期化時に `image_cap_pixels(cfg)` が環境値を参照して上限を決める。得た値は `Service.inkling_image_max_px` に保存される。環境変数をリクエストごとに再読込するコードはなく、起動後の環境変更は反映されない。run config の変更も次回起動から有効。`terminal/serve/server.py:9449-9451,9702-9707`、`terminal/serve/inkling_kind.py:322-337`、`terminal/serve/runconfig.py:7-8`。

画像付きリクエストでは画像を正規化し、上限が非ゼロなら Pillow で画素数を確認する。超過画像は縦横比を保って縮小し、JPEG は JPEG（quality 95）、それ以外は PNG として再エンコードする。縮小できなかった画像はそのままエンジンへ渡す。`terminal/serve/server.py:5691-5701`、`terminal/serve/inkling_kind.py:340-372`。

起動時、上限が非ゼロなら `[strata] pictures: scaled down to at most {上限MP:.2f} MP before the engine reads them (inkling_image_max_mp in the run config, in megapixels, sets another size, 0 turns it off)` を出す。実際に縮小した各画像については `[strata] picture {元幅}x{元高さ} ({元MP:.1f} MP) scaled to {縮小幅}x{縮小高さ} ({縮小MP:.1f} MP) before the engine reads it (its picture reader runs on the CPU; inkling_image_max_mp in the run config sets the size, 0 turns this off)` を出す。CPU picture reader を使う経路では画像の画素数に応じた無音許容時間も別途設定し、許容時間が `engine.silence_s` より大きい場合、`[strata] {枚数} picture(s), {合計MP:.2f} MP in all: the engine's CPU picture reader may take a while, this request may stay silent for up to {秒:.0f} s` を出す。`terminal/serve/server.py:9708-9710,5694-5710`、`terminal/serve/inkling_kind.py:370-372`。

## ログと測定値

この環境変数について Strata が記録するのは上記の上限設定・縮小・CPU picture reader の待ち時間に関するログ。文書化された測定値はコードコメントと `docs/DETAILS.md` にあるが、この文書では実測を行っていない。サーバーが出す具体的なログ条件と文字列は `terminal/serve/server.py:9708-9710,5704-5710`、縮小画像のメッセージ組み立ては `terminal/serve/inkling_kind.py:370-372` を参照。

## 根拠

- backend ごとの既定値、数値変換、範囲、環境値と config の優先順位: `terminal/serve/inkling_kind.py:318-337`
- 画像縮小と失敗時の元データ維持: `terminal/serve/inkling_kind.py:340-372`
- サーバー起動時の適用と無効値での終了: `terminal/serve/server.py:9702-9710`
- リクエスト内での画像処理と CPU reader の待ち時間ログ: `terminal/serve/server.py:5683-5710`
- 設定変更が次回起動から反映されること: `terminal/serve/runconfig.py:7-8`
- 設計資料との照合: `docs/DETAILS.md:539`
