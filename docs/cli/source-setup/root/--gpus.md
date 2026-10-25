# `--gpus`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、更新 wrapper からも委譲） |
| オプション | `--gpus` |
| 別名 | なし |
| 値 | GPU 番号をカンマで区切った2個以上（例: `0,1`）、または `all`。値は1引数として渡す |

## 役割

1つのモデルを複数 GPU にまたがるレイヤー分割で動かす GPU を選びます。NVIDIA の番号は `nvidia-smi` の番号、AMD の番号は setup が列挙する番号です。オプションは `setup.py` のトップレベル parser にあり、setup 用 wrapper は引数をそのまま渡します（`setup.py:8463-8465`、`setup.sh:6-12,76`、`START-HERE.bat:8-10,48-54`）。

## 使い方

初回 setup または既存モデルの設定変更では、たとえば次のように指定します。

```sh
./setup.sh --setup --gpus 0,1
```

Windows では `START-HERE.bat --setup --gpus 0,1` を使います。すでに設定済みのモデルを起動するときは `./setup.sh --gpus 0,1`（Windows: `START-HERE.bat --gpus 0,1`）のように指定でき、そのモデルの選択として保存されます。`--gpus` は `--setup` の有無で parser が分かれていません（parser: `setup.py:8460-8465`、既存モデルの選択: `setup.py:8646-8650`）。

## 値と既定値

- `0,1` のように GPU 番号をカンマ区切りにします。番号は整数として読み取り、2個以上で重複がないことを要求します。要素の前後の空白は `int()` が処理し、空要素は読み飛ばされます。したがって `0,,1` も2番号として解析されます（`setup.py:1660-1674`）。
- `all` は小文字・大文字を区別せず、前後の空白も除いて判定します。NVIDIA では複数 GPU で共有可能と判定されたカードを選びます。該当カードが2枚未満なら失敗します（`setup.py:1660-1667,1640-1643`）。
- AMD では、対応 GPU の中から `all` が選びます。対応する専用メモリ GPU が2枚以上ある場合は UMA/APU を除外してそのカードを選び、そうでなければ対応 GPU 全体を選びます。数値指定は `setup.py` が列挙した AMD GPU 番号を使います（`setup.py:3949-3980`）。
- 指定を省略した場合は、複数 GPU を利用できれば対話選択、それ以外は setup の既定選択に従います。オプション自身の固定の GPU 番号既定値はありません（`setup.py:1774-1790`）。
- GPU 番号の存在と利用可否も確認されます。未知の番号、非対応 GPU、重複番号、1個だけの番号、数値でも `all` でもない値は拒否されます。`all` の結果が2枚に満たない場合も拒否されます。失敗時のメッセージは `fail()` が標準出力に出し、終了コード1で終了します（`setup.py:1660-1674,1677-1703,825-830`）。

## 実行時の動作

初回 setup では、選んだカードを一緒に使う前提でモデルのサイズ選択・メモリ見積もり・engine の対象アーキテクチャを決めます。選択結果は設定の `gpu` 配列として保存され、レイヤー分割の `layer_split` は `--layer-split` がなければ `auto` になります。マルチ GPU 用の engine 設定も行われます（`setup.py:8771-8804,9637-9646`）。

既存モデルの起動時に `--gpus` を渡すと、選択カードをそのモデルの設定へ書き込み、未指定の layer split は既存値または `auto` にします。NVIDIA では各カードが使える engine か確認し、対応コードが足りなければ setup を再実行するよう案内して起動を止めます。AMD では保存したカードが HIP engine のアーキテクチャに含まれるか確認し、不足時は再 setup を案内します（`setup.py:6775-6792,6814-6820,6827-6837,7190-7216`）。

数値を明示した場合、setup は NVIDIA / AMD とも入力順を選択リストに保ちます。`all` の初期候補順は NVIDIA では新しい世代、VRAM、番号順、AMD では UMA でないカード、VRAM、番号順です（`setup.py:1623-1627,1640-1643,3840-3843,3953-3962`）。実際の分割順は起動時にも調整されます。layer split が `auto` で、速度を測定でき、カード間の差が5%を超える場合、server は速いカードを最後（Main stage）へ移します。ただし最後の stage に置く GPU の VRAM が小さくなる場合は元の順を維持します。手動 `--layer-split`、`gpu_order: as_given`、GPU roles がある場合などは自動並べ替えをしません（`serve/server.py:3346-3396`）。

## 適用条件と副作用

- 複数 GPU で共有できないカードは `all` から外れるか、明示指定時に拒否・確認の対象になります。NVIDIA はモデルを分割する各カードに `SPLIT_MIN_VRAM_GB` 以上の VRAM が必要で、明示指定したカードが単体では使えても分割時の VRAM 条件だけを満たさない場合はリスク確認になります。`--yes` と明示的な番号指定の組み合わせはそのリスクへの同意として扱われます（`setup.py:1611-1619,1677-1694,5851-5860`）。
- 初回 setup で AMD の複数 GPU を選ぶ場合、Windows は未対応として停止し、`--gpu N` で単一 GPU を使うよう案内します。複数 AMD GPU の layer split は Linux のみです（`setup.py:8731-8733`）。
- 低 RAM モードでは、明示的な `--gpus` は複数 GPU の選択を維持します。その場合、GPU に載らない expert は常駐 RAM ではなく OS の file cache 経由で読まれ、長い prompt 中に空き RAM がなくなる可能性を警告します（`setup.py:5751-5765`）。モデルや設定によっては複数 GPU を推奨しない分岐があり、`--gpus` がない場合は単一 GPU に戻す選択が行われます（`setup.py:5786-5848`）。
- `--gpu-roles` と `--gpu` / `--gpus` は同時指定できず、parser 後の検査でエラーになります。`--layer-split` は `--gpus` で選択した GPU 間の境界指定で、既定は `auto` です（`setup.py:8466-8470,8578-8597,9640-9646`）。
- `--gpu` と同時に `--gpus` を指定する相互排他検査はありません。通常の GPU 選択関数は `--gpus` を先に処理します（`setup.py:1774-1783`）。
- setup ではモデルや engine の取得・build・設定ファイル作成があり得ます。既存モデルの start ではモデル設定が更新されます。GPU 使用可否や選択結果は標準出力へ表示されます（`setup.py:808-830,8911-8912,9637-9646`）。

## 出力とエラー

不正な指定、利用できない GPU、Windows での複数 AMD GPU 指定などは setup 独自の `[X]` メッセージと案内を標準出力に表示し、終了コード1で停止します（`setup.py:825-830,8731-8733`）。番号の整数変換に失敗する値は `--gpus takes GPU numbers ...`、番号が2個未満または重複なら `--gpus takes two or more different GPUs ...` になります（`setup.py:1668-1674`）。

## 根拠

- parser と help 文: `setup.py:8460-8470`
- 値の解析、GPU 適合性、NVIDIA の共有候補と順序: `setup.py:1611-1643,1660-1703,1774-1790`
- AMD GPU の `all` と番号検査: `setup.py:3874-3920,3949-3980`
- 初回 setup の選択・Windows AMD 制限・設定保存: `setup.py:8731-8804,9637-9646`
- 起動時の GPU 並べ替えと Main stage: `serve/server.py:3346-3396`
- 既存モデル start 時の選択・保存・engine 確認: `setup.py:8646-8650,6737-6749,6775-6837,7190-7216`
- 低 RAM / resident-budget 関連の相互作用: `setup.py:5751-5848`
- setup wrapper の引数委譲: `setup.sh:6-12,76`、`START-HERE.bat:8-10,48-54`、`UPDATE.bat:5-6,79`

## 調査範囲

対象 checkout は commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、branch `main`（`origin/main` と一致）で、`git status --short --branch` は `## main...origin/main` でした。ソース parser と使用箇所を確認しました。CLI `--help` は実行していません。OS・GPU 構成ごとの実行結果や、各 model/backend の全ての条件分岐は実機で確認していません。
