# `--no-remote-expert-opt`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、`SETUP.bat`、`update.sh`、`UPDATE.bat` から委譲） |
| オプション | `--no-remote-expert-opt` |
| 別名 | なし |
| 値 | 取らない。`argparse` の `store_true`。既定値は `False`。 |

## 役割

複数 GPU を使う setup の設定生成で、setup が engine 引数 `--remote-expert-opt` を自動追加するのを抑えます。engine 引数そのものではなく、setup.py の option です。Linux では `setup.sh`、Windows では `START-HERE.bat` が引数を `setup.py` に渡し、`SETUP.bat` は `--setup` を付けて `START-HERE.bat` を呼びます（`setup.sh:6-12`、`START-HERE.bat:44-49`、`SETUP.bat:1-3`）。

## 使い方

既存モデルの設定を複数 GPU 用に作り直し、設定ファイルだけ保存する例です。

```sh
./setup.sh --setup --gpus 0,1 --no-remote-expert-opt --no-start
```

`--gpus` は複数 GPU の選択、`--setup` は設定変更、`--no-start` はモデルを起動せず setup の完了後に戻る指定です。Windows の wrapper でも同じ option を渡せます。

## 値と既定値

この option は値を取りません。`argparse` は `action="store_true"` で宣言しているため、省略時は `False`、指定時は `True` です（`setup.py:8471-8472`）。数値や文字列の範囲 validation はありません。値を続けて渡した場合は余分な引数として parser が拒否します（`setup.py:8420-8421,8553`）。

## 実行時の動作

`main()` が `--setup` 等で新しい run config を組み立て、複数 GPU の `multi` が選ばれた場合、`recommend_remote_expert_opt(cfg, off=a.no_remote_expert_opt)` を呼びます（`setup.py:8620,9640-9646`）。helper cache 用の engine 引数が既存 config にあり、この option が有効なら、その `--remote-expert-opt` を `args` から1件取り除いて関数を終了します。engine 引数の追加・削除後は run config に保存されます（`setup.py:1921-1938,9727-9729`）。option 自体を config に保存する処理はありません。

この option を省略したとき setup が自動追加するのは、選択 GPU が2枚以上で、config に `--expert-cache-device1`〜`--expert-cache-device3` のいずれかがあり、`--pipeline-windows` の正の値が設定されておらず、config の `remote_expert_opt` が `false` ではない場合です。既に `--remote-expert-opt` があれば重複追加しません。単なる layer split で helper cache がなければ追加しません（`setup.py:1932-1959`）。

## 適用条件と副作用

- 効果が確認できるのは、複数 GPU の設定を組み立てる setup 経路です。`--update` は `update_install(have, a)` に分岐し（`setup.py:8617-8619`）、通常起動では `start(...)` が呼ばれます（`setup.py:8677-8682`）。通常起動中の `--gpus` 経路での推奨処理は `recommend_remote_expert_opt(cfg)` と呼ばれ、`a.no_remote_expert_opt` を渡していません（`setup.py:6814-6820`）。従って、この option を通常起動や `--update` に付けても、自動推奨を抑止する経路にはなりません。
- option は自動追加をその実行で抑止し、setup が再生成する `args` から engine option を除去します。以後の setup 実行でも確実に無効を維持する設定として、run config の `"remote_expert_opt": false` が `recommend_remote_expert_opt()` により尊重されます（`setup.py:1935-1938`、`docs/SECOND_GPU.md:87-100` はこの config 設定も説明しています）。
- helper cache がない場合、または単一 GPU の場合、engine 側は `--remote-expert-opt` に対する optimization object を作らず、通常の経路を使います（`src/program/generate.cpp:6662-6665`）。engine parser は `--remote-expert-opt` を serve mode でのみ受け付けます（`src/program/generate.cpp:2568,3365-3367`）。
- `--pipeline-windows` の正の値が config にある場合、setup は自動追加を行いません。既に `--remote-expert-opt` も設定されていれば、両者が競合し engine が pipeline を無効化すると警告します（`setup.py:1939-1950`）。
- config の書き込みは一時ファイル経由の置換です。通常の setup 全体ではモデル・engine 等の準備も行うことがありますが、この option 固有のファイル書き込みは run config の変更です（`setup.py:6154-6159,9727-9729`）。

## 出力とエラー

この option 固有の拒否条件や警告は見つかりませんでした。自動追加された場合は setup が `[ok] multi-GPU: --remote-expert-opt ... --no-remote-expert-opt leaves it out` と表示します。option によって既存引数を除去した場合の専用メッセージはありません（`setup.py:817-822,1935-1938,1956-1959`）。不正な値を付けるなど parser の引数形式に反する呼び出しは `argparse` のエラーになります（`setup.py:8420-8421,8553`）。

engine option が残っていて `--serve` なしで engine を直接呼ぶ場合は、`strata generate: --remote-expert-opt requires --serve` と stderr に出して終了コード2で拒否します（`src/program/generate.cpp:3365-3367`）。これは本 option 自体ではなく、engine に渡される別 option の失敗経路です。

## 根拠

- `setup.py:8420-8421,8471-8472,8553` — parser 宣言、値なし・既定値、引数解析。
- `setup.py:1921-1959` — 複数 GPU・helper cache・pipeline 条件、自動追加と抑止処理。
- `setup.py:6814-6820,8617-8620,9640-9646,9727-9729` — 通常起動・update と setup 時の呼び出し差、および config 保存。
- `setup.py:6154-6159` — run config の書き込み方法。
- `src/program/generate.cpp:2568,3365-3367,6662-6669` — engine 側の対応 option、serve 条件、helper cache がない場合の扱い。
- `docs/SECOND_GPU.md:87-100` — remote expert optimization の概要と持続的 opt-out 設定。

この調査では同一 revision の `setup.py` と参照先ソースを確認しました。CLI `--help` は別途実行していません。GPU backend ごとの性能差は測定していません。
