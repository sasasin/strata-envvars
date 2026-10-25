# `--control-vector-scaled`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata`（エンジン引数） |
| オプション | `--control-vector-scaled` |
| 別名 | なし |
| 値 | `FILE:SCALE`。カンマ区切りで複数組を指定可能 |

## 役割

GGUF 形式の control vector をエンジン起動時に読み込み、モデルの各レイヤーの FFN 書き込み後に残差ストリームへ適用します。指定がなければベクトルは読み込まれません。読み込んだベクトルは通常の生成では有効で、`--serve` ではリクエストごとに有効・無効を切り替えられます（`src/program/generate.cpp:797-803, 953-957, 12304, 12520, 12922-12927`）。

## 使い方

モデルとパックを指定する起動例です。ファイル名とスケールの区切りは最後の `:` です。

```sh
./engine/strata --pack ./packs/model --native ./models/model.gguf \
  --control-vector-scaled ./vectors/style.gguf:0.7 --serve
```

ベクトルの適用レイヤー・方式・方向を調整する場合は、関連する [`--control-vector-layer-range`](--control-vector-layer-range.md)、[`--cvec-mode`](--cvec-mode.md)、[`--cvec-dir`](--cvec-dir.md) も指定します（`src/program/generate.cpp:953-957`）。

## 値と既定値

- 各要素は `FILE:SCALE` で、複数ファイルは `FILE1:SCALE1,FILE2:SCALE2` のように一つの引数内でカンマ区切りにできます。最後のコロンで分割するため、Windows のドライブ文字に含まれるコロンはファイル名側に残ります。ファイル名にカンマを含む場合のエスケープ機能は parser にありません（`src/program/generate.cpp:2703-2716`）。
- `SCALE` は `strtof` で float に変換します。数値の一部しか読めない値、数値が空の値、`FILE` が空の値、区切りのない値は `--control-vector-scaled: expected FILE:SCALE, got ...` を stderr に出し、終了コード 2 で失敗します。有限値かどうかやスケール範囲の追加検証はありません。負値・ゼロも parser では拒否されません（同上）。
- 省略時はファイル一覧が空で、何もロードされません。オプション自体の既定スケールはありません。`--control-vector FILE` を同時に指定すると、そのファイルは scale 1 で同じ一覧へ追加されます（`src/program/generate.cpp:797-803, 2702-2716`）。
- 複数ファイルの同じレイヤーの `direction.<layer>` は、それぞれのスケールを掛けた後に加算されます（`src/program/generate.cpp:1863-1866, 1872-1895`）。

## 実行時の動作

値を受け取った時点ではファイルを読み込まず、モデル初期化後に `load_control_vectors` が実ファイルを開きます。GGUF の `general.architecture` が `controlvector` であることを要求し、`direction.<layer>` テンソルはモデルの埋め込み幅と同じ要素数の f32 でなければなりません。レイヤー 0 とモデル範囲外のテンソルは無視されます。各ファイルに有効な `direction.<layer>` が一つもない場合は失敗します（`src/program/generate.cpp:1867-1901`）。

受理したファイルのベクトルはレイヤーごとに合算されます。既定の適用範囲はレイヤー 1 から最終レイヤーまで（両端を含む）です。実際の適用範囲は `--control-vector-layer-range A B` で指定できます。既定の方式は `add` で、このとき合算ベクトル `d` を加えます。`--cvec-mode project` を指定すると合算ベクトルを単位化して `h ← h − (h·v)v` の射影除去を行い、ベクトルのノルムを係数に使います。ゼロベクトルのレイヤーは適用対象になりません。`--cvec-dir single:L` は project 方式でレイヤー L の方向を範囲内の各レイヤーに使います（`src/program/generate.cpp:801-803, 1903-1930`; `include/strata/kernels/cvec.hpp:5-16`）。

読み込み時に GPU 用のテーブルをアップロードし、レイヤー分割時は処理する各 CUDA デバイスにも複製します。ベクトルは各トークンの各残差ストリームに対して、そのレイヤーの FFN 書き込み後に適用されます（`src/program/generate.cpp:3960-3968, 4368-4371`; `src/core/layer.cpp:1614-1630`; `include/strata/kernels/cvec.hpp:59-63`）。ロード状態・方式・範囲・テーブルはセッション識別 digest にも含まれます（`src/program/generate.cpp:1930-1946`）。

## 適用条件と副作用

- 指定ファイルが開けない、GGUF でない、アーキテクチャ metadata が違う、テンソル形状・型が合わない、対象範囲内に適用可能な方向がない場合、推論開始時に stderr へ `strata generate: control vector: ...` を出し、終了コード 2 で終了します（`src/program/generate.cpp:1872-1901, 1903-1930, 3963-3968`）。
- `controlvector.model_hint` が存在し、値が `qwen4exp` 以外なら stderr にモデル不一致の警告を出しますが、この箇所ではロードを中止しません（`src/program/generate.cpp:1880-1883`）。
- ロード成功時は stderr に方式、方向指定、レイヤー範囲、適用レイヤー数を表示します。`--serve` の `INFO` 行には `cvec=<mode>:<first>-<last>` が含まれます（`src/program/generate.cpp:1942-1946, 11078-11092`）。
- `--serve` はリクエスト属性 `cvec=0|1` を読み、属性が省略されたときは有効として扱います。ロード済みの場合に限って有効・無効を切り替え、状態が変わると live session やチェックポイントの再利用条件を更新します（`src/program/generate.cpp:12304, 12325-12339, 12520, 12922-12927`）。ロードされていない場合、この属性だけではベクトルは適用されません。
- 通常の CUDA 実装ではロード時にデバイスメモリを確保し、失敗するとロードエラーになります。また、適用カーネル起動の失敗は例外として呼び出し元へ伝わります（`src/kernels/cuda/cvec.cu:26-39, 101-132, 162-171`; `src/core/layer.cpp:1628-1630`）。
- Metal エンジンでは `cvec()` が空の状態を返す実装であり、このオプションは移植されていません。Metal でのロード・適用はできません（`metal/src/engine/missing.cpp:32-40`; `docs/MAC.md:257`）。SYCL 側には同オプションの parser とカーネル実装ファイルがありますが、この調査では対応する各種デバイス・モデルでの実行は確認していません（`sycl/src/program/generate.cpp:1980-1993`; `sycl/src/kernels/cuda/cvec.dp.cpp`）。
- Strata に同梱される実験用 speed projection は Qwen3.8-Flash-Next 向けの control vector で、説明文書は拒否方向の射影除去と安全挙動への影響を記載しています。任意の vector の挙動やモデル適合性をこの同梱例から一般化できません（`data/experimental-speed-projection/README.md:3-17`）。

## 出力とエラー

- 引数が `FILE:SCALE` 形式でない場合は parser が stderr にエラーを出して終了コード 2 を返します（`src/program/generate.cpp:2703-2716`）。
- ファイル読み込み・GGUF 検査等に失敗すると、エラー理由を stderr に出して終了コード 2 を返します（`src/program/generate.cpp:1872-1901, 3963-3968`）。
- 未知の引数は `unknown argument: ...` と usage を表示して終了コード 2 になります（`src/program/generate.cpp:2787-2792`）。

## 根拠

- 索引上のスコープとリンク: `docs/cli/README.md:1128-1148`（`strata-engine` の root parser と対象オプション）。
- オプション parser と usage: `src/program/generate.cpp:953-957, 2702-2732`。
- GGUF 読み込み、テンソル検査、複数方向の集約、適用テーブル構築: `src/program/generate.cpp:1863-1946`。
- 残差への適用と GPU 実装: `include/strata/kernels/cvec.hpp:5-16, 59-63`; `src/core/layer.cpp:1614-1630`; `src/kernels/cuda/cvec.cu:42-95, 101-171`。
- `--serve` のリクエスト切替: `src/program/generate.cpp:12304, 12325-12339, 12520, 12922-12927`。
- プラットフォーム制約と実験用 vector の説明: `metal/src/engine/missing.cpp:32-40`; `docs/MAC.md:257`; `data/experimental-speed-projection/README.md:3-17`。
