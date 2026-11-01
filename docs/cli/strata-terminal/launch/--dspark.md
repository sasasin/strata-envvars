# `--dspark`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--dspark` |
| 別名 | なし |
| 値 | `on`、`off`、`auto`、`none` のいずれか（必須） |

## 役割

DeepSeek V4.1 用 engine の DSpark drafter（先読みするドラフター）を制御します。DeepSeek 以外を対象にしたオプションではありません。`strata launch` は指定値を起動設定の engine 引数 `--dspark VALUE` に反映します。

## 使い方

```sh
strata launch --model ist-das-2.00bpw --dspark auto --no-tui
```

実際に使用するモデル名はインストール済みモデルに合わせてください。プリセットから起動する場合も同じ起動フラグを付けられます。

## 値と既定値

- 値は前後の空白を除去し、小文字化してから `on`、`off`、`auto`、`none` と照合されます。別の値は parser が拒否し、近い候補があれば候補名も示します（`strata_cli/launch/cmd.py:37-44,117-119`）。
- 値を省略できません。省略時は argparse が usage とエラーを stderr に出し、終了コード 2 で終了します。
- `--dspark` 自体を省略した場合、launch は保存済みモデル設定の engine 引数をそのまま引き継ぎます。標準の DSV41 setup は macOS 以外で `auto`、macOS で `none` を設定します（`setup.py:8733-8745`）。engine を直接起動した場合の `Options` 初期値は `auto`（有効かつ自動判定）です（`src/dsv41/ds4_model.hpp:46-55`）。

## 実行時の動作

launch は値を `s.extra["--dspark"]` に格納し、実行用設定を作る際に argv の変更として保存済み engine 引数へ適用します（`strata_cli/launch/cmd.py:284-290`、`strata_cli/launch/runner.py:524-565,1438-1454`）。値の意味は DSV41 engine で次のとおりです（`src/dsv41/ds4_main.cpp:1332-1337`）。

| 値 | engine での意味 |
| --- | --- |
| `auto` | DSpark を自動判定する。 |
| `on` | DSpark を有効にし、自動判定による無効化を行わない。 |
| `off` | 推測デコードを止めるが、DSpark のロード要求は残す。 |
| `none` | DSpark をロードしない。 |

`auto` は pack にドラフト層（MTP）があり、かつルーティング対象 experts のサイズが GPU の空き容量（reserve を差し引いた合計）の 1.5 倍を超えると、ロードを取りやめます。その際 engine は、推測ラウンドが通常の token より多くのデータを読み、速度向上がない条件である旨を stderr に出します。容量が条件を超えなければロードします（`src/dsv41/ds4_model.cu:2338-2351`）。ドラフト層が pack にない場合もロード対象になりません（同 `src/dsv41/ds4_model.cu:2329-2338`）。

同じ設定は `--set dspark=VALUE` でも渡せます。両方を指定した場合、`--set` の値を取り込んだ後で `--dspark` の値を設定するため、専用オプションの値が優先します（`strata_cli/launch/cmd.py:284-290`）。`--set` 経由では専用 option の選択肢 validation は通りません。設定変換側は `--dspark` を単語値として小文字化して渡す仕様です（`strata_cli/launch/settings.py:280-310`）。

## 適用条件と副作用

- 標準 DSV41 setup は `auto` を設定し、macOS 向け設定は `none` を設定します。macOS engine は `auto` でドラフターをロードしないよう補正して stderr に通知します。明示的な `on` は警告を出した上でロードを試み、Metal に未対応の Markov bias kernel で engine が停止する可能性があります（`setup.py:8733-8745`、`src/dsv41/ds4_model.cu:2326-2336`）。
- `off` は `none` と異なり、DSpark のロードを止めません。engine の parser では `off` の場合も `o.dspark` は true のままで、推測デコード用 `spec` だけ false になります（`src/dsv41/ds4_main.cpp:1332-1337`）。したがって、ドラフターのメモリ使用も避けたい場合は `none` を指定します。
- DSpark は DSV41 engine の option です。別の model/backend の engine が `--dspark` を受け付けることはこの調査では確認できていません。別 engine へ渡した場合は未対応 option として起動に失敗する可能性があります。DSV41 以外での互換性は未確認です。

## 出力とエラー

- `strata launch` で選択肢外の値を指定すると parser が値エラーを報告します。値を省略した場合も argparse の引数エラーとなり、どちらも launch 処理に入る前に終了します（`strata_cli/launch/cmd.py:37-44,117-119`）。
- DSV41 engine に値が届かない（例: `--set dspark=`）場合、設定変換は空値を変更なしとして扱い、元の engine 設定を保ちます（`strata_cli/launch/settings.py:286-300`）。
- engine parser は `--dspark` の値を要求し、不足時は stderr に `--dspark needs a value` を出して終了コード 2 で終了します。未知の engine option は stderr に `unknown option ...` と usage を出し、2 で終了します（`src/dsv41/ds4_main.cpp:1307-1315,1380-1385`）。
- `auto` によるロード見送りと macOS の未対応通知は engine の stderr 出力です（`src/dsv41/ds4_model.cu:2329-2346`）。その後の起動成否や利用者側に表示されるログ位置は engine 起動経路にも依存するため、ここでは固定の表示先を断定しません。

## 根拠

- `strata_cli/launch/cmd.py:117-119` — `strata launch` の parser 定義と値の選択肢。
- `strata_cli/launch/cmd.py:284-290` — CLI 値を起動設定に取り込む処理、macOS での `on` 警告、`--set` との優先関係。
- `strata_cli/launch/runner.py:524-565,1438-1454` — engine 引数への変換と起動用設定の生成。
- `strata_cli/launch/settings.py:280-310` — `--dspark` を単語値として扱う規則。
- `src/dsv41/ds4_main.cpp:1307-1315,1332-1337,1380-1385` — engine parser の値要求、4値の意味、エラー経路。
- `src/dsv41/ds4_model.hpp:46-55`、`src/dsv41/ds4_model.cu:2326-2351` — engine 既定値、macOS 条件、`auto` の GPU 容量判定とロード制御。
- `setup.py:8733-8745` — 標準 DSV41 setup が config に書く値（非 macOS `auto`、macOS `none`）。
