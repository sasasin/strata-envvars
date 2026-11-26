# `source-setup --vision-tokens`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` |
| オプション | `--vision-tokens` |
| 別名 | なし |
| 値 | 整数 `N`。通常の setup 経路では 1 以上 |

## 役割

画像 encoder が1枚の画像を処理するときに許す画像 token 数の上限を指定する。setup は値をモデルの run config の `vision.max_tokens` に保存し、サーバーは画像 reader の `--max-tokens` として渡す。値を大きくすると細かい文字や図を読める場合がある一方、encoder の処理時間や GPU reader の VRAM 使用量が増える。parser は画像処理の有効・無効を `--vision` で別に選ぶ。

## 使い方

```sh
# CPU の画像 reader に1画像あたり最大768 tokenを設定して setup する
./setup.sh --setup --vision cpu --vision-tokens 768
```

## 値と既定値

- parser は `N` を `int` に変換する。通常の setup 経路では `N < 1` を `argparse` のエラー経路に送り、メッセージは `--vision-tokens takes a number of image tokens, 1 or more` とする。parser 登録と値検査は `terminal/setup.py:11466-11469`、`terminal/setup.py:11641-11642`。
- parser に上限値の検査はない。画像 reader の GPU 時既定値は `1024`、CPU 時は `300`。setup は GPU の既定値を超える値では VRAM と context の増加を、CPU の既定値を超える値では処理時間増加を案内する。`terminal/setup.py:8725-8747`、既定値は `terminal/setup.py:950-951`。
- 省略時は、同じモデルの既存 config に `vision.max_tokens` があり、現在選択された reader device（GPU/CPU）と一致し、正の整数で既定値と異なる場合、その値を引き継ぐ。それ以外は device の既定値を使う。`terminal/setup.py:8725-8739`。
- 値は setup の再実行で同じ encoder device の既存値を保つ。ただし `--vision` で CPU/GPU を切り替えると、旧値は引き継がれず切替後 device の既定値（または今回の明示値）になる。`terminal/setup.py:8730-8737`。

## 実行時の動作

画像 reader が有効な場合、setup は選択値を `vision.max_tokens` に入れた config を生成する。通常の setup と Control setup の両経路で同じ `vision_tokens` 関数を呼ぶ。`terminal/setup.py:10021-10032`、`terminal/strata_control/setup_config.py:561-571`。Apple Silicon の setup 経路もこの値を vision 設定に含める。`terminal/setup.py:11352-11360`。

サーバーは config 値を整数化し、正値なら画像 reader の `--max-tokens N` として起動引数に追加する。値がない場合は reader 種別の既定値を使う。`terminal/serve/server.py:3106-3129`。値が既定値より大きくても setup 側では上限に丸めず、案内のみを出す。`terminal/setup.py:8725-8747`。

## 適用条件と副作用

- `--vision` が画像 reader を無効にする設定の場合、この値は使われず warning が出る。通常経路では `--vision-tokens: images are off, so it is not used`、Control 経路では `--vision-tokens: images are off for this model, so it is not used` と出力する。`terminal/setup.py:10022-10034`、`terminal/strata_control/setup_config.py:561-573`。
- 選択した engine に画像 encoder がない場合、setup は画像を無効化する。この場合も `vision_tokens` は設定されない。`terminal/setup.py:9933-9940`、Control の engine component 経路は `terminal/setup.py:9484-9489`。
- config の `vision.max_tokens` は起動時に reader の上限へ反映される。reader 設定に明示された値は既定値に置き換えられない。`terminal/serve/server.py:3107-3129`。
- setup は run config を書き換える。既存 config と内容が異なる場合、先に `.bak` を作成し、backup 作成に失敗したときは warning を出して続行する。`terminal/setup.py:7715-7747`。

## 出力とエラー

`N < 1` は setup.py の `ap.error(...)` を通る。値を整数に変換できない場合も argparse parser が拒否する。画像 reader が無効なら値を無視した warning を出す。値が有効な場合、setup は選んだ token 数、device 別既定値、および該当する処理時間または VRAM/context の注意を表示する。`terminal/setup.py:8725-8747`、`terminal/setup.py:11641-11642`。

## 根拠

- `terminal/setup.py:11463-11469` — setup.py の vision 関連 option parser。`--vision-tokens` は整数値を取り、vision の reader 選択とは別 option。
- `terminal/setup.py:11635-11642` — SYCL の委譲分岐後に行う正数検査。SYCL やそれ以前に委譲される platform-specific 経路の個別 parser 挙動はここでは確認していない。
- `terminal/setup.py:8725-8747`、`terminal/setup.py:950-951` — 既存値の再利用、GPU/CPU 既定値、利用者への注意表示。
- `terminal/setup.py:10021-10034`、`terminal/strata_control/setup_config.py:561-573`、`terminal/setup.py:11352-11360` — 画像有効時の config 設定と無効時の warning。
- `terminal/serve/server.py:3106-3129` — `vision.max_tokens` を reader の `--max-tokens` 引数にする処理。
- `terminal/setup.py:7715-7747` — run config 書き込みと変更時の backup。
