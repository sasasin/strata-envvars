# `--gpus`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` / update wrappers |
| オプション | `--gpus` |
| 別名 | なし |
| 値 | GPU 番号をカンマ区切りで2個以上指定するか `all`。NVIDIA は `nvidia-smi` の番号、AMD は setup が列挙する番号を使う |

## 役割

モデルを複数 GPU に割り当てる指定です。インストール時（`--setup` を含む）は選択 GPU をモデル設定に保存し、通常はモデルのレイヤー分割に使います。インストール済みモデルの起動時に指定した場合も、その GPU 群をモデル設定へ保存して起動します。GPU の選択は単一の設定値ですが、実際の分割方法は backend とモデルのエンジン経路に依存します。

## 使い方

```sh
# NVIDIA GPU 0 と 2 を使ってモデルをセットアップ
./setup.sh --setup --gpus 0,2

# 対応する複数 GPU を自動選択してセットアップ
./setup.sh --setup --gpus all

# インストール済みモデルを GPU 0 と 2 で起動し、この選択を保存
./setup.sh --gpus 0,2
```

Windows では `START-HERE.bat` に同じオプションを渡します。AMD の番号は setup が表示する番号です。

## 値と既定値

- `0,2` のような番号列は整数へ変換され、少なくとも2個かつ重複なしでなければなりません。空要素は無視されるため、たとえば `0,,2` も解析上は `0,2` と同じになります。整数でない値、番号が1個だけの値、重複番号はエラーです。番号の存在や利用可能性は後続の GPU 検査で確認されます（`terminal/setup.py:2226-2240`）。
- `all` は前後の空白を除いて大文字小文字を区別せず認識されます。NVIDIA 経路では、Strata が同時利用可能と判定した GPU を選びます。選択できる組み合わせがなければ GPU 一覧を表示し、失敗します（`terminal/setup.py:2226-2233`）。
- 省略時の値は parser 上 `None` です。セットアップでは GPU の自動選択または対話的な選択へ進み、起動時は保存済み GPU 設定を使用します（`terminal/setup.py:11491-11493`、`terminal/setup.py:2340-2361`、`terminal/setup.py:11725-11728`）。
- GPU 番号列の形式は AMD でも同じですが、AMD の `all` は対応 AMD GPU を選ぶ専用 parser を通ります。AMD 起動時の `all` は NVIDIA 側で適合 GPU が見つからない場合などにも AMD の一覧から解決されます（`terminal/setup.py:2323-2337`、`terminal/setup.py:11838-11863`）。

## 実行時の動作

セットアップ時は `parse_gpus` で値を解決した後、選択カードを検査します。明示した GPU が見つからない、あるいは Strata がその backend で利用できない場合は GPU 一覧・候補と理由を出して失敗します。明示したカードが単独では利用可能でも、複数 GPU でのモデル共有に必要な VRAM が不足する場合はリスク確認を行います。`--yes` を付けた場合はこの確認への同意として扱われます（`terminal/setup.py:2243-2269`）。

選択した GPU の集合はモデル設定の `gpu` として記録され、通常の複数 GPU 構成では `layer_split` が未指定なら `auto` になります。CUDA では適合性確認後、必要なエンジンコードの確認やリモート expert 設定の推奨も行います（`terminal/setup.py:8640-8646`）。AMD 経路でも複数 GPU を `gpu` に保存し、レイヤー分割として起動します（`terminal/setup.py:8614-8617`、`terminal/setup.py:11840-11863`）。

インストール済みモデルの起動時に指定すると、起動処理が `--gpus` を GPU 番号へ解決し、選択をモデル設定へ保存してから起動します。対して `--gpu N` はその起動だけの単一 GPU 指定です（`terminal/setup.py:11725-11729`、`terminal/setup.py:8607-8647`）。

## 適用条件と副作用

- `--gpu-roles` と `--gpus` / `--gpu` は併用できず、同時指定は parser 後の検証でエラーになります（`terminal/setup.py:11652-11667`）。`--gpu` と `--gpus` の両方が指定された場合に別の競合エラーはなく、セットアップ選択では `--gpus` が優先されます（`terminal/setup.py:2340-2349`）。
- `--layer-split` は `--gpus` に対応する分割境界の指定です。GPU 選択を保存する通常経路では明示した `--layer-split` を保存し、未指定なら `auto` を使います（`terminal/setup.py:11491-11498`、`terminal/setup.py:8614-8616`、`terminal/setup.py:8640-8646`）。
- 対応動作はモデル経路ごとに異なります。Qwen3.6 の独自エンジン経路では CUDA の2 GPU指定が `--peer-device` による第2カードの expert tier として構成され、2枚以外の指定は1枚だけで動く旨の警告を出します（`terminal/setup.py:9844-9851`、`terminal/setup.py:9985-10011`）。したがって `--gpus` の受理だけで、全モデルが同じ方式の分割を行うとは限りません。
- セットアップでモデル設定ファイルを書き換えます。起動時の指定も後続起動に使う GPU 選択として保存されます（`terminal/setup.py:8614-8617`、`terminal/setup.py:8640-8646`）。モデルのダウンロードや起動など、他のセットアップ処理の副作用も起こり得ます。
- `--check` と組み合わせた場合も GPU 選択・適合性確認を行いますが、モデル適合表へ渡されるのは選ばれた代表 GPU の情報です。適合するモデルがなければ終了コード `1`、チェック成功なら `0` で終了し、モデルをインストールしません（`terminal/setup.py:11883-11889`、`terminal/setup.py:11960-11979`）。

## 出力とエラー

形式不正、重複、GPU が1個だけの指定は `fail` により説明と例を出して拒否されます。`all` で利用できる GPU 組み合わせがない場合は GPU 表を表示して失敗します。指定 GPU が見つからない、または利用できない場合も GPU 表・代替候補とともに失敗します（`terminal/setup.py:2226-2239`、`terminal/setup.py:2243-2269`）。引数 parser の `ap.error` による他オプションとの競合はエラー終了になります（`terminal/setup.py:11652-11667`）。

## 根拠

- `terminal/setup.py:11491-11493` — parser 定義とヘルプ上の値形式・番号体系。
- `terminal/setup.py:2226-2240` — NVIDIA 側の文字列解析、`all`、個数・重複・整数検証。
- `terminal/setup.py:2243-2269` — GPU 存在・利用可否、VRAM不足時の確認、失敗経路。
- `terminal/setup.py:2323-2337`、`terminal/setup.py:11838-11863` — 起動時およびセットアップ時の AMD 番号解決・選択。
- `terminal/setup.py:11652-11670` — `--gpu-roles` との排他と GPU role からの選択反映。
- `terminal/setup.py:11725-11729`、`terminal/setup.py:8601-8647` — インストール済みモデルの起動時指定、設定保存、単一 GPU 指定との違い。
- `terminal/setup.py:9844-9851`、`terminal/setup.py:9985-10011` — Qwen3.6 固有の2 GPU時の構成。
- `terminal/setup.py:11883-11889`、`terminal/setup.py:11960-11979` — `--check` での GPU 選択情報と終了経路。

調査範囲は Strata checkout のソースです。実機ごとの GPU 列挙結果、ドライバーや外部 backend の実行時挙動、各モデルでの性能差はこのソース調査では確認していません。
