# `--dsv41-package`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat` などの wrapper 経由も同じ） |
| オプション | `--dsv41-package` |
| 別名 | なし |
| 値 | `FILE`: DeepSeek エンジンのアーカイブ、または展開済み package directory |

## 役割

DeepSeek-V4.1 用の別配布エンジン package を指定します。通常の feed からの取得に代えて、指定した package を検査して `engine-dsv41` に導入します。Strata の通常エンジンとは別の場所に置かれます（`setup.py:7764-7778`、`strata_control/dsv41_engine.py:1-6`）。

## 使い方

Strata checkout のルートで、たとえば次のように `deepseek41` を選択して使います。

```sh
python setup.py --family deepseek41 --dsv41-package /path/to/strata-dsv41-package.tar.gz
```

同じ引数は `./setup.sh --family deepseek41 --dsv41-package ...`、Windows の `START-HERE.bat --family deepseek41 --dsv41-package ...` に渡せます。POSIX wrapper は `setup.py` に全引数を渡し（`setup.sh:6-12,76`）、Windows wrapper も同じスクリプトを呼びます（`START-HERE.bat:8-11,44-55`）。`--family` の選択肢に `deepseek41` があることと、その family が DeepSeek 用処理へ分岐することは `setup.py:8421-8424,8932-8937` に定義されています。

## 値と既定値

値は必須で、parser では `metavar="FILE"` の通常文字列として受け取ります。既定値はありません。help は `.tar.gz`、`.zip`、または展開済みフォルダを案内しています（`setup.py:8489-8490`）。実装は `.tar.gz`、`.tar.xz`、`.zip` のファイル名を受け付け、ディレクトリも受け付けます。`Path(...).expanduser()` により `~` を展開します（`strata_control/dsv41_engine.py:38-39,58-75`）。他の拡張子のファイル、存在しないパス、無効な package は導入されません。

## 実行時の動作

指定値は DeepSeek のセットアップ経路で `get_dsv41_engine()` に渡されます。指定時は `install_package()` を実行し、feed 取得へ進みません（`setup.py:7770-7796`）。導入前に manifest の存在、実行ファイル名が現在の OS 用 `strata-dsv41` であること、対象 platform、信頼鍵による署名、および manifest 内の全ファイル hash を確認します（`strata_control/dsv41_engine.py:51-54,76-99`）。展開上限は 8 GiB です（同 `:38-39,70-75`）。

package は `engine-dsv41/<version>-<platform>-<backend>[-<variant>]/` に置かれます。既存の同名 version directory は削除して置き換え、検査後に他の directory も削除してこの package 一世代だけを残します（`strata_control/dsv41_engine.py:100-110`）。一時作業ディレクトリ `engine-dsv41.manual` は処理後に削除されます（同 `:62-65,115-116`）。

## 適用条件と副作用

- この引数が実際に使われるのは `--family deepseek41` などで DeepSeek の `install_dsv41()` 経路に入ったときです。別 family のセットアップでは package を導入しません（`setup.py:8932-8937`）。
- 既に `dsv41_exe()` が実行可能な DeepSeek engine を見つけた場合、`setup.py` は `get_dsv41_engine()` を呼ばないため、指定 package の検査・導入は行われません。その場合も package 指定時は自動 upgrade 条件から外れます（`setup.py:8040-8052`）。
- DeepSeek engine が見つからず `--build` も指定されていなければ、手動 package の検査・導入が実行されます。`--build` を併用すると取得処理を飛ばし、engine が見つからない場合は利用可能 engine がないとして停止します（`setup.py:8045-8058`）。
- macOS の通常 setup は parser を作る前に `metal/setup_mac.py` へ引数を委譲します。この文書で確認した `setup.py` parser と DeepSeek installer の適用対象外です。委譲先に同 option があるかはこの調査では確認していません（`setup.py:8418-8424`）。
- `setup.py` のこの引数自体は値の形式検査をせず、package installer がファイル・署名・内容を検査します。新規導入ではエンジン package のファイル書き込み・削除が発生します。モデルデータのダウンロードやその後の setup の副作用は他の引数・処理にも依存します。

## 出力とエラー

指定 path が存在しない、対応外の拡張子、manifest がない、別の engine/package、別 platform、署名や hash の検証失敗、展開・導入時の I/O error などは理由を stdout に出し、installer は `None` を返します（`strata_control/dsv41_engine.py:58-60,70-97,112-114`）。呼び出し側は「指定 package を利用できなかった」と案内して `fail()` し、setup を終了コード 1 で停止します（`setup.py:7775-7778,825-830`）。導入失敗時は一時作業 directory を finally で削除します（`strata_control/dsv41_engine.py:115-116`）。

## 根拠

- parser と値の説明: `setup.py:8489-8490`
- family の選択・分岐: `setup.py:8421-8424,8932-8937`
- package 使用条件、feed 取得との分岐、既存 engine 時の扱い: `setup.py:7770-7796,8040-8058`
- package の path、形式、展開・検査・配置: `strata_control/dsv41_engine.py:38-39,51-116`
- wrapper の引数委譲: `setup.sh:6-12,76`、`START-HERE.bat:8-11,44-55`、`SETUP.bat:1-3`、`update.sh:5-7,62`、`UPDATE.bat:5-6,79`

調査範囲は上記 commit の checkout 内ソースです。安全な同一 revision の CLI `--help` 実行、および公式 Release artifact の実体確認は行っていません。記載した archive 形式と validation は parser・installer のソースから確認しています。
