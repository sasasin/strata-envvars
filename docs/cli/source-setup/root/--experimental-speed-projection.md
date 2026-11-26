# `setup.py --experimental-speed-projection`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` から委譲されるセットアップ CLI） |
| オプション | `--experimental-speed-projection` |
| 別名 | なし |
| 値 | `on` / `off` / GGUF ファイルパス。実装では大文字小文字を区別しない on/off の別表記も受け付ける |

## 役割

モデルのセットアップ時に、実験的な control vector を engine の起動設定へ含めるか選びます。標準ベクトルを指定する場合は `on`、無効にする場合は `off`、別のベクトルを使う場合は GGUF ファイルパスを指定します。標準ベクトルは Qwen3.8-Flash-Next と Coder の経路でのみ有効化されます。

## 使い方

```sh
# Linux / Windows: Qwen モデルの設定を作成し、モデルは起動しない
./setup.sh --setup --family qwen --model IQ3_S --experimental-speed-projection on --no-start

# 同じ設定で実験的な投影を無効にする
./setup.sh --setup --family qwen --model IQ3_S --experimental-speed-projection off --no-start

# 標準ベクトルの代わりに独自 GGUF を指定する
./setup.sh --setup --family qwen --model IQ3_S --experimental-speed-projection /path/to/vector.gguf --no-start
```

`--no-start` を付けてもセットアップ処理と設定ファイルの書き込みは行われます。オプションだけを指定して既存インストールを通常起動する場合、保存済み設定は変更されず、その設定で起動します。

## 値と既定値

parser は `metavar="on|off|GGUF"` のみを指定し、`choices`、`type`、明示的な `default` は設定していません（`terminal/setup.py:11485-11487`）。値が省略された場合、Qwen / Coder のセットアップでは対話質問が表示され、既定回答は `n`（off）です。`--yes` で質問を省略する場合も、この質問の既定回答は off です（`terminal/setup.py:12279-12286`）。

実装では前後の空白を除去してから判定します。`off`、`no`、`n`、`0` は無効、`on`、`yes`、`y`、`1` は同梱ベクトルを選択します。判定は小文字化して行うため大文字小文字は区別されません。それ以外の文字列は `~` 展開・絶対パス化した GGUF のパスとして扱われ、ファイルが存在しなければエラーで終了します（`terminal/setup.py:12277-12290`）。

## 実行時の動作

セットアップする family が `qwen` または `coder` の場合、値が空なら上記の対話選択を行い、on または独自パスなら対象ファイルが通常ファイルとして存在することを確認します。off なら `esp` は未設定のままです。独自パスについて GGUF の内容、形式、互換性まではこのオプション処理では検証しません（`terminal/setup.py:12277-12291`）。

投影が有効なとき、設定生成処理は engine の引数へ `--control-vector-scaled <path>:1.0 --control-vector-layer-range 4 44 --cvec-mode project --cvec-dir per-layer` を追加します（`terminal/strata_control/setup_config.py:429-432`）。この設定はモデルの run config に保存され、後続の起動で使われます（`terminal/setup.py:12521-12527`）。run config から設定を引き継ぐ新しい checkout のセットアップでは、保存済みの投影設定が CLI 値未指定時に再利用されます（`terminal/setup.py:11701-11712`、`terminal/setup.py:7818-7828`）。また、run config の `user_args` に利用者が手動で登録した control-vector 引数はセットアップ時にも生成引数へ重ねて適用されます。そのため、既存の手動設定がある場合、このオプションを `off` にしてもその手動設定までは除去しません（`terminal/setup.py:7632-7656`、`terminal/strata_control/user_args.py:7-16`）。

投影ベクトルを含む設定では、web app と API のリクエスト単位で投影を切り替えられます。サーバーは `experimental_speed_projection` が boolean のとき `cvec=0|1` を engine に渡し、この機能が未ロードの engine ではキーを出しません（`terminal/serve/server.py:1438-1445`）。

既存モデルを通常起動する経路では、セットアップ用オプションとして扱われません。既存設定があり `--setup`、`--check`、モデル・family 指定等がない場合は保存済み run config をそのまま起動します（`terminal/setup.py:11734-11739`、`terminal/setup.py:11761-11775`）。設定を変更する場合は `--setup` を指定してください。

## 適用条件と副作用

- 標準の投影処理は `qwen` / `coder` family の分岐でのみ有効です。その他の family で on 相当またはパスを指定すると警告を出して投影を無効のまま続けます。`swift` には元の Qwen3.8-Flash-Next 用である旨、それ以外にはそのモデルで未テストである旨を表示します（`terminal/setup.py:12292-12294`）。
- Apple Silicon の通常セットアップは `terminal/setup.py` から `engine/metal/setup_mac.py` に引き渡されます。同 Mac parser は未知の引数を受け取ると「not used on a Mac」と警告して無視するため、このオプションは Mac の Metal セットアップでは適用されません（`terminal/setup.py:11436-11437`、`engine/metal/setup_mac.py:372-405`）。
- セットアップで run config が変更されると、同名の既存 config は `.bak` にコピーされる経路があります（`terminal/setup.py:7715-7744`）。
- この設定はモデルの回答時の挙動を変える実験的な投影であり、速度向上を保証するものではありません。独自 GGUF の内容・互換性や、各モデルでの品質・性能はこの parser / 設定生成コードからは確認できません。

## 出力とエラー

有効化時は `[ok] experimental speed projection: ON (experimental)`、無効時は `[ok] experimental speed projection: off` を表示します（`terminal/setup.py:12291`）。対応外 family では警告して処理を続けます（`terminal/setup.py:12292-12294`）。選択したパスがファイルでない場合は不足パスを表示し、`fail()` が終了コード 1 でセットアップを停止します（`terminal/setup.py:12289-12290`、`terminal/setup.py:1049-1056`）。値を伴わずオプションだけを渡した場合は、argparse の parser が引数エラーとして扱います（定義: `terminal/setup.py:11485-11487`、parse: `terminal/setup.py:11606`）。

## 根拠

- `terminal/setup.py:11485-11487` — root parser 定義と help 表示。
- `terminal/setup.py:12277-12294` — 既定の質問、値の分類、存在確認、family ごとの適用・警告。
- `terminal/strata_control/setup_config.py:429-435` — engine 引数への投影設定追加と run config の組み立て。
- `terminal/setup.py:11734-11775`、`terminal/setup.py:12521-12527` — 通常起動とセットアップ分岐、設定ファイルへの反映。
- `terminal/serve/server.py:1438-1445` — API / web リクエストの投影状態を engine 引数へ渡す処理。
- `engine/metal/setup_mac.py:372-405`、`terminal/setup.py:11436-11437` — Mac で別 parser に委譲し未知引数を警告付きで無視する処理。
