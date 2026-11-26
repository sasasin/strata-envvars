# `--control-vector`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`strata generate` と同じ root parser） |
| オプション | `--control-vector` |
| 別名 | なし |
| 値 | control vector 形式の GGUF ファイルパスを 1 つ |

## 役割

GGUF の control vector を読み込み、推論中の residual stream に加算します。`--control-vector` は指定した各ファイルを scale `1` として登録します。複数のファイルを指定した場合や `--control-vector-scaled` と併用した場合は、同じ層の方向ベクトルが読み込み時に加算されます。制御ベクトルを使う要求の既定値は有効です。

## 使い方

```sh
# pack と token ID 列を指定して通常の生成を行う
engine/strata --pack /path/to/pack --tokens "1,2,3" --control-vector /path/to/control-vector.gguf
```

`--control-vector` は次の argv 要素をファイルパスとして受け取ります。help の例では `--pack DIR` と `--tokens LIST` が基本引数として示され、通常モードでは token input が必須です。`--serve` では要求が token を持ち込むため、`--tokens` を省略できます。

## 値と既定値

- 値は 1 つのファイルパスです。parser はパスの存在・空文字列・拡張子を事前検証せず、各指定を `{path, 1.0f}` として追加します。同じオプションを複数回指定できます（`engine/src/program/generate.cpp:3842-3847,4164`）。
- 未指定時は control vector を読み込まず、適用しません。`--control-vector-scaled FILE:SCALE[,...]` も同じリストに追加されるため、両方を指定するとそれぞれ scale 1 と指定 scale の項が合算されます（`engine/src/program/generate.cpp:1202,1370-1372,4164-4178`）。
- 読み込む GGUF の `general.architecture` は `controlvector` である必要があります。`direction.<layer>` tensor はモデル埋め込み次元数の f32 でなければならず、切り詰められた tensor も拒否されます。層 0 とモデル層数以上の tensor は無視されます。指定範囲に方向が一つも残らない場合も失敗します（`engine/src/program/generate.cpp:2743-2784,2786-2813`）。
- 既定の適用範囲は全層 `1..最終層`、既定 mode は `add` です。これらは `--control-vector-layer-range` と `--cvec-mode` で変わります（`engine/src/program/generate.cpp:1203-1205,1372-1374,2786-2809`）。

## 実行時の動作

モデルの初期化時に登録済みファイルを GGUF として開き、各 `direction.<layer>` の値へそのファイルの scale を掛けて同じ層ごとに加算します。このオプション単独の scale は `1.0` です。GGUF の `controlvector.model_hint` があり、値が `qwen4exp` 以外の場合は stderr に警告しますが、そこで読み込みを拒否する分岐ではありません（`engine/src/program/generate.cpp:2748-2780`）。

読み込んだ方向は既定で各層の residual stream に加算されます。`--cvec-mode project` の場合は指定方向に沿う成分を除く処理になります。層範囲は両端を含み、未指定・0 以下の開始値は 1、未指定・0 以下または層数以上の終了値は最終層に補正されます（`engine/src/program/generate.cpp:2786-2813`; 演算は `engine/src/kernels/cuda/cvec.cu:45-95`）。

`--serve` では要求行の `cvec=0|1` キーで要求ごとに有効・無効を切り替えられます。キーを省略したときの要求値は `1` です。要求値は `atoi` で整数化され、0 は無効、0 以外は有効として扱われるため、`0|1` 以外を拒否する validation はありません。実際に vector がロード済みの場合だけ要求値を適用します。切替時は live session と checkpoint を破棄してから device 側の有効フラグを切り替えます。vector をロードしていない場合、`cvec` キーは vector の有無を変えません（`engine/src/program/generate.cpp:18835,18882-18889,19149,20048-20053`; device flag の更新は `engine/src/kernels/cuda/cvec.cu:137-150`）。

## 適用条件と副作用

- ファイルの読み込みと vector table の GPU upload は、モデル初期化時に `cvec_files` が空でない場合に行われます。upload に失敗したデバイスでは初期化が失敗し、層 split の各デバイスへの複製失敗も起動エラーになります（`engine/src/program/generate.cpp:6143-6150,6693-6697`; `engine/src/kernels/cuda/cvec.cu:26-39,101-135`）。
- control vector は層の FFN write 後の residual stream に適用されます。prefill 経路にも vector 適用箇所があり、融合条件を満たさない場合は個別の適用 kernel を呼びます（`engine/src/core/layer.cpp:1637-1653`; `engine/src/prefill/prefill.cpp:7659-7721`）。
- 読み込み時に model hint 不一致の警告、mode・範囲・steered 層数の情報を stderr に出します。serve の `INFO` 行には vector の mode と層範囲の要約が出ます（`engine/src/program/generate.cpp:2756-2758,2825-2829,16200-16214`）。
- GPU kernel は CUDA 実装を確認しました。HIP/SYCL 等、他 build の制御 vector 実装や全 backend での挙動差は、この調査範囲では確認していません。

## 出力とエラー

- `--control-vector` の値が欠けると `--control-vector needs a value` を stderr に出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3846`）。
- ファイルを開けない、GGUF の architecture が異なる、方向 tensor の型・次元・payload が不正、方向 tensor がない、または適用層に方向がない場合、loader のエラー文字列を `strata generate: control vector: ...` として stderr に出し、終了コード 2 を返します。GGUF 読み込み例外も同じ経路に渡されます（`engine/src/program/generate.cpp:2750-2784,2812-2813,6145-6150`）。
- device upload に失敗した場合は loader が失敗を返し、上記の control vector load error 経路になります。split 先の複製失敗は CUDA デバイス番号とエラーを stderr に出し、終了コード 1 で終了します（`engine/src/kernels/cuda/cvec.cu:26-39,101-120`; `engine/src/program/generate.cpp:6693-6697`）。

## 根拠

- `engine/src/program/generate.cpp:1199-1205` — option に対応する設定、未指定値、mode・範囲の既定値。
- `engine/src/program/generate.cpp:1370-1374,3842-3847,4164-4188` — help 文言、値の取得、scale 1 の登録、関連する範囲・mode parser。
- `engine/src/program/generate.cpp:2743-2830,6143-6150` — GGUF の検証・合算・範囲解決・GPU upload・失敗処理。
- `engine/src/program/generate.cpp:18835,18882-18889,19149,20048-20053` — serve 要求の `cvec` 値、既定、session/checkpoint の切替処理。
- `engine/src/kernels/cuda/cvec.cu:45-95,101-150` — add/project の kernel 演算、upload と serve 中の有効フラグ更新。
- `engine/src/core/layer.cpp:1637-1653`, `engine/src/prefill/prefill.cpp:7659-7721` — 推論層と prefill での適用箇所。
