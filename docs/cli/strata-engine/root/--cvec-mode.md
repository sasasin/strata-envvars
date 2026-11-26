# `--cvec-mode`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数） |
| オプション | `--cvec-mode` |
| 別名 | なし |
| 値 | `add` または `project` |

## 役割

ロードした control vector を各対象層の残差ストリームにどう適用するかを選ぶ。`add` は方向ベクトルを加算し、`project` は残差から方向ベクトルへの射影成分を差し引く。control vector を指定していない場合、このモードによる処理は行われない。

## 使い方

```sh
# control vector をロードして、射影成分を除去するモードで生成
strata generate --pack ./pack --tokens "1,2,3" \
  --control-vector-scaled ./vector.gguf:1.0 \
  --control-vector-layer-range 4 44 --cvec-mode project
```

## 値と既定値

- `add`: 既定値。各残差ストリーム `h` にスケール済み方向 `d` を加える（`h += d`）。
- `project`: 各層の方向を単位ベクトル `v` に正規化し、`h` から `s (h·v) v` を引く。`s` はスケール済み方向のノルム。
- 値は大文字小文字を含めて `add` または `project` と一致する必要がある。ほかの値は `--cvec-mode: add or project, got '…'` を stderr に出し、終了コード 2 で引数処理を中止する。値を省略すると「needs a value」を stderr に出して終了コード 2。
- 同じ引数を複数回指定した場合、parser は該当値をその都度代入するため、最後に指定した値が残る。

## 実行時の動作

parser は `project` を内部値 0、`add` を 1 に設定する。control vector のファイルが指定されているとき、GGUF の `direction.<layer>` テンソルを読み、指定ファイルの方向とスケールを合算する。`project` では合算方向のノルムを層ごとの係数として保存し、カーネルが `h - s(h·v)v` を計算する。`add` では合算方向をそのまま保存し、カーネルが `h + d` を計算する。適用は層の FFN 書き込み後で、control vector が存在する層に限られる。

このオプション単独では vector をロードしない。`--control-vector` または `--control-vector-scaled` で少なくとも1つ指定した場合にロード処理が走り、そのモードが使われる。未指定なら vector はロードされず、モード値は推論に作用しない。ロードした vector とモードはセッション識別情報に含まれる。

`--control-vector-layer-range` は適用層の両端を指定し、省略時のロード処理は層 1 から最終層までを対象にする。`--cvec-dir single:L` は `project` のときだけ、全対象層で層 `L` の方向を使う。`add` のときは per-layer 扱いとなり、`single:L` の指定は方向選択に反映されない。

`--serve` では、ロード済み vector をリクエストごとに有効・無効にできる。リクエストの `cvec=0` は無効、`cvec=1` またはキー省略は有効で、モード自体は起動時に指定した値のまま。切替時には会話キャッシュの live 状態を無効化し、vector を保持するデバイスの同期と有効フラグ更新を行う。

## 適用条件と副作用

- vector の GGUF は `general.architecture` が `controlvector` である必要がある。該当テンソルがない、テンソルが埋め込み幅の f32 でない、ペイロードが切れている、対象層に方向がない場合などはロードに失敗する。
- `project` で指定した `single:L` に方向がない場合もロード失敗となる。`single:L` の整数部分は `atoi` で読み取られ、文字列全体の数値形式検証は parser では行われない。
- mode とロードした方向データはカーネル用テーブルとしてデバイスへアップロードされる。アップロードに失敗した場合はロード失敗となる。
- これらのロード失敗は `strata generate: control vector: …` を stderr に出して終了コード 2。ファイルの形式・テンソル検証と失敗位置は `load_control_vectors` の実装に基づく。

## 出力とエラー

vector のロード成功時は stderr にモード、方向選択、層範囲、実際に方向がある層数を出力する（例: `control vector mode = project, dir = per-layer, layers 4..44 (...)`）。起動時の server 情報行には `cvec=<mode>:<first>-<last>` の要約が含まれる。`--cvec-mode` 自体に固有のファイル書き込みやネットワーク副作用は確認できなかった。

## 根拠

- `engine/src/program/generate.cpp:1202-1205` — vector ファイル一覧、既定モード `add`、内部値、方向選択状態。
- `engine/src/program/generate.cpp:1370-1374` — help の値説明と control vector 関連オプション。
- `engine/src/program/generate.cpp:3842-3846,4184-4188` — 値の取得、欠落値の終了、許容値と不正値の処理。
- `engine/src/program/generate.cpp:2743-2830` — GGUF の検証、層ごとの方向と係数、mode 別テーブル構築、アップロード、識別情報および stderr 要約。
- `engine/src/program/generate.cpp:6143-6150` — vector 指定時だけのロードと失敗時の終了コード 2。
- `engine/include/strata/kernels/cvec.hpp:5-16,25-36` — 適用式、層範囲、vector がない場合の状態。
- `engine/src/kernels/cuda/cvec.cu:45-92` — kernel が `project` / `add` を計算する実装。
- `engine/src/core/layer.cpp:1638-1649` — FFN 書き込み後に対象層へ適用する経路。
- `engine/src/program/generate.cpp:18835,18882-18889,19149-19150,20048-20053` — serve リクエストの `cvec` 値、既定有効、状態切替え。
- `engine/src/program/generate.cpp:2815-2823,14013-14016` — mode を含む vector digest をセッション識別情報に設定。

調査対象 checkout は `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`、作業状態は `## main...origin/main`（未コミット変更なし）。GPU 実行・build は行っていないため、実行時のデバイス別成否や数値上の効果は測定していない。
