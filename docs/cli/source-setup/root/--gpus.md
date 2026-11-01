# `--gpus`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat`、更新 wrapper から委譲） |
| オプション | `--gpus` |
| 別名 | なし |
| 値 | 複数 GPU の番号をカンマ区切りで指定（例: `0,2`）、または `all` |

## 役割

1つのモデルを複数 GPU に分割して実行する GPU を指定します。モデル設定時は選択をそのモデルの設定に保存し、通常起動時はその起動に使う GPU を指定して設定にも記録します。`--gpu` は1枚用です。`setup.py` の parser は `--gpus` を値を取る文字列引数として定義しています（`setup.py:9113-9115`）。

## 使い方

```sh
./setup.sh --setup --gpus 0,2
./setup.sh --gpus all
```

Windows では `START-HERE.bat --setup --gpus 0,1` のように wrapper へ渡します。wrapper は `setup.py` に委譲します（索引の対象境界: `docs/cli/README.md:13`）。`--setup` を付けた例はモデルの設定時、2つ目は既に設定済みのモデルの起動時です。起動時に `--gpus` を省略した場合は保存済み選択を使い、条件が合えば複数 GPU の利用を一度確認します（`setup.py:9309-9312`）。

## 値と既定値

- 値は `0,2` のような整数番号の列、または前後の空白を除いて大文字小文字を無視した `all` です。引数自体は必須ではなく、未指定時の既定値は `None` です（`setup.py:9113-9115`）。
- 番号列では空の要素を読み飛ばし、整数化した後、2個以上かつ重複なしを要求します。そのため `0,,2` の空要素は無視されます。`0` だけ、同じ番号の重複、整数でない要素は失敗します（`setup.py:1836-1850`）。空文字列は後段で未指定と同様に扱われます（`setup.py:1933-1937`）。
- NVIDIA では番号は `nvidia-smi` の番号です。番号が未検出、または選択 GPU が利用不可なら停止します。複数利用時に VRAM が共有要件に足りないカードを番号で明示した場合は、確認を出し、`--yes` があれば同意として続行します。`all` は Strata が同時利用可能と判定したカードだけを選び、該当カードがなければ停止します（`setup.py:1838-1849`、`setup.py:1853-1870`、`setup.py:1950-1956`）。
- AMD では番号は Strata の AMD/HIP 一覧順です。番号指定時は各 GPU が AMD backend で利用可能か確認します。`all` は利用可能なカードを `amd_rank` 順に選び、専用メモリを持つ GPU が2枚以上ある場合は UMA（システム共有メモリ）のカードを除外します。除外カードを番号で明示すれば選択対象にできます（`setup.py:4217-4248`）。

## 実行時の動作

モデルの setup 経路では NVIDIA の番号列を検証し、指定順で選択結果を構成します。選択が複数なら設定の `gpu` に番号リスト、`layer_split` に `--layer-split` の値または `auto` を保存し、モデル層を複数 GPU に分割します。セットアップ設定はモデルごとの JSON に書き込まれます（`setup.py:1950-1956`、`setup.py:9464-9472`、`setup.py:10338-10347`、`setup.py:10436-10454`）。AMD の指定番号列では最初のカードが main として扱われます（`setup.py:4217-4220`、`setup.py:9420-9444`）。

既存モデルの起動時にも `--gpus` の番号を解決します。NVIDIA ではカードを確認後、GPU リストと自動 layer split をそのモデルの設定へ保存します。AMD の HIP 経路でもカードリストを設定へ保存し、インストール済み engine に選択カードのアーキテクチャ向けコードがない場合は起動を止めて、その GPU 向けの再 setup を案内します（`setup.py:1933-1947`、`setup.py:7157-7167`、`setup.py:7196-7204`）。

選択した GPU 数は `--replicas` のグループ分けにも関わります。replica 数が2以上でも、複数選択がない場合や GPU 数を等分できない場合、replica 設定は行われず警告になります（`setup.py:10361-10384`）。複数 GPU 設定では helper cache 条件に応じて engine 用の `--remote-expert-opt` が自動追加されることがあります。setup 側の `--no-remote-expert-opt` で抑止できます（`setup.py:2105-2142`、`setup.py:10341-10347`）。

## 適用条件と副作用

- `--gpu-roles` と同時には指定できません。両方があると parser 処理でエラーになります。`--gpu` にカンマ区切り値を渡すと、`--gpus` へ移し替えられます。両方に別々の値を渡した場合の明示エラーはなく、setup の GPU 選択では `--gpus` が優先されます（`setup.py:9232-9242`、`setup.py:1950-1959`）。
- `--backend hip` で AMD GPU を使う Windows の setup では複数 GPU 分割を拒否し、`--gpu N` を案内します。この判定は setup 経路にあります（`setup.py:9395-9398`）。
- `--gpus all` は全ての検出 GPU を無条件に選ぶ指定ではなく、backend ごとの利用可能性や AMD の UMA 条件を反映します（`setup.py:1838-1843`、`setup.py:4221-4230`）。
- 選択はモデル単位の設定に保存されるため、setup の実行ではモデル設定ファイルが更新されます。複数 GPU 分割用の `layer_split` も既定で `auto` として記録されます（`setup.py:10341-10347`）。

## 出力とエラー

`setup.py` の独自検証失敗は理由と修正案を表示して `SystemExit(1)` で終了します（`setup.py:904-910`）。番号列の形式不正、番号不足・重複、GPU 未検出・利用不可では `--gpus` の形式例や利用可能な GPU、代替コマンドを表示します（`setup.py:1844-1849`、`setup.py:1858-1870`、`setup.py:4232-4247`）。AMD の Windows setup で複数 GPU を指定した場合もエラーと単一 GPU の案内を出して停止します（`setup.py:9395-9398`）。

## 根拠と調査範囲

根拠は指定 revision の Strata ソース `setup.py` の parser、選択・検証処理、setup 設定保存、起動時処理です。コマンド scope と予定リンクは strata-envvars の索引 `docs/cli/README.md:1528-1557` で確認しました。CLI help や実機 GPU での実行は調査していません。GPU 検出・適合性の個別基準は `gpu_problem` / `amd_problem` 等の helper の判定に依存し、この文書では GPU driver や外部 runtime 自体の動作までは扱いません。
