# `setup.py --drafter`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` からも引数を転送） |
| オプション | `--drafter` |
| 別名 | なし |
| 値 | `mtp`、`dflash2`、`dfly2`、`dspark`、`off` のいずれか。省略時は `None` |

## 役割

モデルのセットアップ中に、ドラフターの取得やモデルに含めるドラフター関連ファイルを選ぶ引数です。ただし、値の意味はモデル系列で異なります。Qwen 系では主に DFlash2 と MTP の取得経路を選び、Inkling-2-Mini では `off` かどうかで DSpark を含めるかを決めます。Hy4-Flash のセットアップ処理はこの引数を参照しません。

## 使い方

```sh
# Qwen 系のセットアップで DFlash2 を使う選択にし、モデル起動は後で行う
./setup.sh --setup --family qwen --model IQ3_S --drafter dflash2 --no-start

# Inkling-2-Mini のセットアップで DSpark を含めない
./setup.sh --setup --family inkling-2-mini --drafter off --no-start
```

`setup.sh` は `setup.py` に引数をそのまま渡します（`setup.sh:14-18`）。Windows の `START-HERE.bat` も `%*` を `setup.py` に渡します（`START-HERE.bat:49-56`）。

## 値と既定値

- parser は上記5値を `choices` で受理し、既定値は `None` です。短縮名、独自の型変換、明示的な `required` 指定はありません（`terminal/setup.py:11357-11364`）。
- 不正な値は `argparse` の選択肢検証で拒否されます。parser の解析は `main()` で行われます（`terminal/setup.py:11385`）。
- 値を省略した場合、Qwen 系で MTP がまだない新規セットアップでは、ハードウェア・モデルに応じた Terminal の Auto 判定が DFlash2 を選ぶことがあります。MTP が既にある場合、`--mtp` が指定されている場合、または Auto が MTP を選ぶ場合は、この自動切替はありません（`terminal/setup.py:8963-8978`、`12111-12118`）。

## 実行時の動作

**Qwen 系:** `dflash2` の場合、MTP の約5.2 GB の取得見積もりと MTP 取得を抑止し、DFlash2 用語彙ファイルを用意します（`terminal/setup.py:12117-12121`、`12264-12273`）。明示した `--drafter dflash2` は自動選択フラグではないため、セットアップ中の `fetch_dflash2_drafter()` 呼び出しには入りません。同関数による取得は、未指定時の Auto 判定が DFlash2 を選んだ経路に限られます（`terminal/setup.py:12112-12113`、`12260-12266`）。明示的に DFlash2 を選んで取得も行う場合は、parser の説明にある別コマンド `strata drafting fetch` を使う経路です（`terminal/setup.py:11361-11364`）。

Qwen 系で `dflash2` 以外の値を渡すと、Auto による DFlash2 の自動選択は抑止されますが、`--mtp off` も指定しない限り通常の MTP 取得分岐は残ります（`terminal/setup.py:8969`、`12112-12118`、`12262-12273`）。この処理では `--drafter` の値そのものを `drafting` 設定へ書き込む箇所を確認できません。`--mtp off` は別引数で、設定に `mtp: false` を書く処理があります（`terminal/strata_control/setup_config.py:539-549`）。したがって、Qwen 系で `--drafter off` を指定しても、それだけで永続設定上のドラフター無効化を意味するとは確認できません。`dfly2` と `dspark` も Qwen 系ではそれぞれのエンジン用ドラフターに切り替える処理が見当たりません。

未指定時の Auto 判定が DFlash2 を選び、その取得に失敗した場合は警告を出し、MTP の取得へ戻します。これは自動選択経路の挙動です（`terminal/setup.py:8981-9005`、`12260-12273`）。一方、明示的な `dflash2` のセットアップはこの自動取得・MTP fallback の条件には該当しません。

**Inkling-2-Mini:** 値が `off` なら DSpark を要求せず、生成する run config の `drafting` を `off` にします。それ以外の4値はすべて同じく DSpark を要求し、config には `inkling_family.DEFAULT_DRAFTER` を設定します。従って `mtp` や `dflash2` はこの系列では MTP / DFlash2 への切替指定ではありません（`terminal/setup.py:10605-10606`、`10617-10623`、`10646-10658`、`10669-10704`）。ローカル GGUF に必要な DSpark が見つからない場合は、そのモデルの `drafting` を `off` にします（`terminal/setup.py:10617-10620`、`10670`）。通常の取得経路で必要ファイル分の空き容量が足りなければ `fail()` でセットアップを中断します（`terminal/setup.py:10622-10632`）。

**Hy4-Flash:** parser は値を受理しますが、Hy4 の run config は `hy4_family.DEFAULT_DRAFTER` から作られ、このオプションを参照する処理は確認できません（`terminal/setup.py:10278-10279`）。

## 適用条件と副作用

- Qwen 系で `dflash2` または Auto による DFlash2 選択になった場合、MTP のドラフト層（約5 GB）の代わりに DFlash2 関連ファイルを使うセットアップ経路になります。明示的な `dflash2` はこのオプション単独では DFlash2 を取得しません（`terminal/setup.py:12117-12121`、`12260-12273`）。
- Inkling-2-Mini では、`off` 以外を指定すると取得ファイル一覧に DSpark が含まれ得ます。ローカルファイルの探索またはモデルファイルのダウンロード・空き容量確認に影響します（`terminal/setup.py:10617-10632`、`10646-10658`）。
- 既存のドラフト層があるかどうか、モデルの family、GPU backend / architecture / VRAM などが Qwen 系の Auto 判定・取得見積もりに関係します（`terminal/setup.py:8963-8976`、`12111-12121`）。

## 出力とエラー

- 不正値は parser が usage とエラーを出して終了します（`terminal/setup.py:11361-11364`、`11385`）。
- Auto による DFlash2 取得が失敗すると、理由を含む警告を出して MTP 取得へ進みます（`terminal/setup.py:8997-9005`、`12260-12273`）。
- Inkling の DSpark を含む取得経路で空き容量不足の場合、必要容量と `--data-dir` / `--models-dir` の案内を出して中断します（`terminal/setup.py:10630-10632`）。

## 根拠

- `terminal/setup.py:11361-11364` — parser 定義、受理値と help 文。
- `terminal/setup.py:8963-9005`、`12111-12121`、`12260-12280` — Qwen 系の Auto 判定、MTP の取得見積もり、DFlash2 と MTP の分岐・fallback。
- `terminal/setup.py:10605-10632`、`10646-10704` — Inkling の DSpark 選択、取得ファイルと run config の構築。
- `terminal/setup.py:10278-10279` — Hy4 の run config に使う既定値。
- `terminal/strata_control/setup_config.py:539-549` — `--mtp` が設定ファイルへ反映される別経路。

調査範囲はこの checkout の Strata 所有ソースです。DFlash2 ファイルの配布元内部の処理や、モデル起動時に最終選択されるドラフターの全条件は本オプションのセットアップ処理だけでは確定できないため、ここでは断定していません。
