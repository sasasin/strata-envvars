# `GPUS`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Docker イメージの entrypoint に複数 GPU を指定し、1モデルを GPU 間の layer split で実行させます。`GPUS` は Strata エンジンや `setup.py` が環境から直接読む変数ではありません。`docker-entrypoint.sh` が値を `--gpus` 引数へ変換し、`setup.py` が GPU を選択してモデル設定へ保存します。Docker を介さず `setup.py` を使う場合は、環境変数ではなく `--gpus` を指定します。

## 値と判定

entrypoint は `GPUS="${GPUS:-}"` として値を取り込み、空でなければ `--gpus "$GPUS"` を setup と起動の両方に渡します。未設定と空文字は同じ扱いで、引数を渡しません。空白だけの値は空とはみなされず、`--gpus` として渡されて setup で形式エラーになります。判定は entrypoint の起動時に行われます。

| 値 | setup 側の扱い |
|---|---|
| 未設定または空文字 | GPU 指定なし。setup の通常選択に委ねます。単一 GPU を選ぶ場合があり、既存の単一 GPU 設定を起動するときは、複数 GPU が利用可能なら一度だけ併用を提案する経路があります。 |
| `all` | `strip().lower()` 後に一致すれば、同時利用可能な GPU 全体を選びます。NVIDIA は `together_ok()` の順序、AMD は利用可能カードを VRAM 順に選びます。2枚以上が選べなければ停止します。 |
| GPU 番号列（例 `0,2`） | カンマ区切り要素を整数化します。前後空白は許容され、空要素は無視されます。2個以上の異なる番号が必要です。実在性・対応可否は続けて検査されます。 |
| その他の文字列 | 整数化やカード検査に失敗した場合はエラーメッセージを表示して終了コード1で停止します。 |

`all` の比較は前後空白と大文字小文字を正規化します。数値列は各要素を `int()` で変換するため、数値文字列として解釈できない要素は拒否されます。範囲外・未検出の GPU、非対応カードも拒否されます。NVIDIA と AMD では GPU 番号の基準が異なり、NVIDIA は `nvidia-smi` の番号、AMD は setup が列挙する番号です。Windows HIP では複数 AMD GPU の layer split は未対応で、複数指定時に停止します。

## 有効になる条件

- `GPUS` が空でなく、指定されたカードがその PC と選択 backend で利用可能であることが必要です。NVIDIA は同時利用可能性、カードの VRAM・エンジン対応などを検査します。AMD は Strata がサポートする HIP デバイスかを検査します。
- 値 `all` は複数 GPU が共有利用可能な場合に限り有効です。番号指定も2枚以上必要で、単一 GPU には `GPU` / `--gpu` を使います。
- `GPUS` と `GPU` の両方が entrypoint に設定されている場合、`setup.py` の GPU 選択では複数指定が優先されます。`GPUS` と `LAYER_SPLIT` が併用されると、後続 GPU の layer 開始位置を指定できます。未指定時は `auto` です。
- Docker 起動時に `/data` の既存モデル設定を使う場合、entrypoint は通常 setup をやり直しませんが、起動時にも `--gpus` を渡します。`setup.py` は選択を設定ファイルに保存して、そのモデルを指定カードで起動します。`REINSTALL=1` の setup 時も `GPUS` は再度 `--gpus` に変換されます。
- `CONFIG` が指定されるとそのファイルが起動対象になります。起動引数の `--gpus` はこの設定に対しても処理されます。

## 実行時の詳細

Docker entrypoint は初回 setup または `REINSTALL=1` の際、非空の `GPUS` を `setup.py --setup --yes ... --gpus <値>` として渡します。通常起動時にも同じ値を `setup.py --port ... --gpus <値>` として渡します。したがって値の変更は entrypoint の次回起動で反映され、環境変数を読んで保持する常駐 cache はありません。setup 起動時には `--gpus` の選択を設定に保存し、GPU ごとの layer split 設定を反映します。`--layer-split` がなければ既存値または `auto` が使われます。

setup は `--gpus all` を NVIDIA の同時利用可能カード、または利用可能な AMD カードに展開します。番号列では指定順が main GPU を含む順序になります。選択不能な GPU や引数形式の誤りでは、setup は理由と修正案を表示して終了します。正常な場合は GPU の組み合わせと layer split を表示し、設定に基づいて server を起動します。Docker では `STRATA_EXECV` が設定されているため、setup プロセスは server に置き換わります。

環境変数名 `GPUS` の参照は Docker 用 `docker-entrypoint.sh` にあります。`tools/batch_groups_cache_test.py` にも同名の読み取りがありますが、これはテストツール専用であり、製品の環境変数動作の根拠にはしていません。`setup.py` の動作は環境変数の直接読み取りではなく、entrypoint から渡される `--gpus` 引数に対する処理です。

## 根拠

- `docker-entrypoint.sh:28,50-53,76-87,96-105` — 値の取り込み、空値なら引数を省略する処理、setup 時・通常起動時の `--gpus` 変換。
- `setup.py:1043-1057,1060-1086` — NVIDIA 向けの `all` / 番号列 parse、件数・重複・利用可能性の検査。
- `setup.py:1116-1130,2164-2188` — 起動時の GPU 分岐、AMD 番号体系と `all` の選択・検査。
- `setup.py:1133-1157,1280-1297` — install 時の選択優先順位と、明示選択がない設定への複数 GPU 提案。
- `setup.py:4314-4321,4343-4357,4380-4409` — 保存済み設定の読み込み、指定カード・layer split の保存、選択カードの確認。
- `setup.py:4852-4859,4990-4995,5065-5069` — CLI 引数、起動時に `--gpus` を優先する処理、Windows AMD 複数 GPU の制限。
- `setup.py:331-336,4438-4443` — エラー時の停止表示と Docker での server 起動。
- `docs/MULTI_GPU.md:1-12,35-66`、`docs/INSTALL.md:118-125`、`Dockerfile:25-40` — layer split と Docker 利用例。これらはソース挙動の補助資料として参照。
