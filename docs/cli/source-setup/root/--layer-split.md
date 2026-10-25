# `--layer-split`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（setup / start wrapper が引数を委譲） |
| オプション | `--layer-split` |
| 別名 | なし |
| 値 | `auto` または後続 GPU ごとの開始 layer 番号をカンマ区切りで指定（例: `18`、`16,32`） |
| 既定値 | parser 自体は省略時 `None`。複数 GPU の設定では `auto` が使われる |

## 役割

複数 GPU で1つのモデルを動かす際、2枚目以降の GPU に割り当てる layer 範囲の開始位置を指定します。数値は各 GPU に割り当てる layer 数ではなく、後続 stage が担当を始める layer 番号です。たとえば `16,32` は layer 0–15、16–31、32 以降という境界を表します（`setup.py:8468-8470`、`serve/server.py:3010-3014`）。

## 使い方

setup で2枚の GPU を使い、2枚目の担当を layer 18 から始める例です。

```sh
./setup.sh --setup --gpus 0,1 --layer-split 18
```

3枚の GPU で境界を2つ指定する例です。

```sh
./setup.sh --setup --gpus 0,1,2 --layer-split 16,32
```

Windows でも `START-HERE.bat --setup --gpus 0,1 --layer-split 18` のように同じ `setup.py` の parser へ引数が渡ります。POSIX setup wrapper は `setup.py "$@"`、Windows setup wrapper は `setup.py %*` を起動します（`setup.sh:12,76`、`START-HERE.bat:48,53`）。

## 値と既定値

parser は `--layer-split` の値を文字列として受け取り、`type`、`choices`、明示的な `default` を指定していません。値の指定自体は必要で、省略した場合の値は `None` です（`setup.py:8468-8470`）。

複数 GPU の setup では、値が省略された場合に `auto` を設定します。既存モデルの起動で複数 GPU を選び直す場合は、指定値、既存設定の値、`auto` の順で採用します（`setup.py:9640-9645,6788-6791,6814-6820`）。

手動値は、後続 GPU ごとに1個の整数をカンマ区切りで指定します。server は前後の空白を除いて整数へ変換し、GPU が `n` 枚なら `n-1` 個であること、空でないこと、最初の値が2以上であること、以降も厳密に増加することを検証します。server が正規化してから engine に渡すため、たとえば ` 16, 32 ` は `16,32` になります（`serve/server.py:3015-3040`）。

モデルの総 layer 数に対する上限は server の形式検査ではなく engine 側で確認します。境界が最後の layer 番号以上なら engine はエラーを出して終了コード2を返します（`src/program/generate.cpp:5132-5136`）。

## 実行時の動作と相互作用

- `--layer-split` は `--gpus` と組み合わせて複数 GPU の layer split を構成するための setup option です。setup は選択された GPU 配列とともに値をモデルの run config の `layer_split` として保存します。`--gpus` を伴わない setup では `multi` がない限りこの保存処理に入りません（`setup.py:9637-9646`）。
- インストール済みモデルの起動で GPU 配列を指定すると、setup は `layer_split` を設定へ保存し、RAM 使用量の split 対応調整などを実施します（`setup.py:6737-6749,6788-6791,6814-6820`）。既存設定を引き継いで再 setup すると、以前の GPU 配列と `layer_split` が再利用される経路もあります（`setup.py:8640-8645`）。
- server は複数 GPU が設定され、engine 引数に `--peer-device` がない場合を layer split として扱います。config の値を検証し、engine 引数に `--layer-split <値>` を追加します（`serve/server.py:3055-3058,3077-3081,3115-3116`）。同じ起動で `--peer-device` を使う構成は layer split ではなく peer expert tier として扱われます。
- engine parser は `--layer-split` の値を受け取ります。layer split の実行条件では `--serve` が必要です。手動境界と GPU 数などの整合性を確認した後、境界に基づいて各 stage の layer 範囲を設定します（`src/program/generate.cpp:2633,2998-3027,5138-5159`）。この setup 経路は serve を起動するため、この条件を満たす起動に値を渡します。
- `auto` は各 GPU の空き VRAMをもとに engine が配置を決める値です。手動値を指定した場合は配置境界がその値に固定されます。複数 GPU 時、engine は stage ごとの担当 layer 範囲を標準エラーに出力します（`setup.py:8468-8470`、`src/program/generate.cpp:6602-6608`）。
- `--replicas` と組み合わせて1 replica あたり複数 GPU となると、setup は手動 `--layer-split` が1つの engine 用の値である旨を警告し、`auto` を使うよう案内します。この警告だけで手動値は拒否されません（`setup.py:9655-9668`）。

## 出力と失敗経路

setup parser 自体は境界値の形式を検証しません。値なしは argparse の usage / error となります。形式不正、GPU 数と境界数の不一致、2未満または昇順でない境界は、server の起動前検査で `ValueError` となり、`[strata] config ...` の診断で停止します（`setup.py:8468-8470`、`serve/server.py:3015-3040,8385-8390`）。

値が形式上正しくてもモデルの layer 数に収まらない場合、engine は `strata generate: --layer-split: layer ... is past the last ...` を標準エラーに出し、終了コード2で終了します（`src/program/generate.cpp:5132-5136`）。自動配置で有効な分割が見つからない場合も別の engine エラー経路がありますが、配置成立は GPU、空き VRAM、モデルなどに依存し、この調査では実機で確認していません。

## 根拠

- `setup.py:8468-8470` — setup parser の定義と help 文
- `setup.py:6788-6791,6814-6820,9637-9646` — 値の保存と複数 GPU 設定への適用
- `setup.py:8640-8645,8674-8691` — 既存設定の引き継ぎと start への値の受け渡し
- `serve/server.py:3010-3040,3055-3058,3077-3081,3115-3116,8385-8390` — 検証、適用条件、engine 引数への変換、失敗出力
- `src/program/generate.cpp:2633,2998-3027,5132-5159,6602-6608` — engine parser、実行条件、境界適用、出力
- `setup.sh:12,76`、`START-HERE.bat:48,53` — wrapper の引数委譲
- [`--gpus`](--gpus.md)、[`複数 GPU の説明`](../../../MULTI_GPU.md) — 関連文書

## 調査範囲

調査対象 checkout は commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`、branch `main`（`origin/main` と一致）です。`git status --short --branch` は `## main...origin/main` で、未コミット変更の表示はありませんでした。source-setup の parser、run config への保存、server の検証と engine 引き渡しを確認しました。同一 revision の CLI `--help` は補助資料として実行していません。各 OS・backend・GPU 構成での起動、Release 配布物との照合、build、GPU 実行、性能測定、テストは行っていません。
