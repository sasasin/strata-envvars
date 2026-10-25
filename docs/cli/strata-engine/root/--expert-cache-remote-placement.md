# `--expert-cache-remote-placement`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main` (`origin/main`) で、調査時点の作業ツリーに変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジン） |
| オプション | `--expert-cache-remote-placement` |
| 別名 | なし |
| 値 | `stripe` または `layer`（大文字小文字を区別） |

## 役割

CUDA1〜CUDA3 に置く remote expert cache 間で、CUDA0 の cache に入らなかった expert をどのように分配するか指定します。`stripe` は expert の layer/expert ペアを各 remote GPU に順番に割り当て、`layer` は layer 番号を基に担当 GPU を決めます。既定値は `stripe` です。

この指定が割り当てに反映されるのは、CUDA1 の remote cache に加えて CUDA2 または CUDA3 にも remote cache を設定した場合です。CUDA1 だけを使う場合は、値の検証は行われますが、全順位を CUDA1 に渡す経路となり、この配置値による分配は行われません。

## 使い方

CUDA1 と CUDA2 の remote cache を使い、layer ごとに担当 GPU を分ける例:

```sh
strata --serve --pack /path/to/model.pack \
  --expert-profile /path/to/expert-profile.bin --expert-cache 4096 \
  --expert-cache-device1 2048 --expert-cache-device2 2048 \
  --expert-cache-remote-placement layer
```

expert の順位を複数 GPU に交互に分けるには `layer` を `stripe` にします。モデルや推論方式に必要な他の engine 引数も指定してください。

## 値と既定値

- 省略時は `stripe`。
- `stripe` と `layer` だけが有効です。その他の値は parser 後の検証で stderr に `strata generate: --expert-cache-remote-placement must be stripe or layer` と出して終了コード `2` になります。
- 値は次の引数として受け取ります。値を省略すると `--expert-cache-remote-placement needs a value` を stderr に出して終了コード `2` で終了します。
- 同じ option を複数回指定すると、引数を走査した後に設定値として残るのは最後の値です。

## 実行時の動作

remote cache を使用するには、`--expert-cache-device1` が正の容量であり、`--expert-cache` が正、expert profile が読み込まれており、expert pool が有効である必要があります。条件を満たさないと remote cache 初期化箇所でエラーを出し、終了コード `2` で終了します。CUDA2/3 を指定する場合も CUDA1 が必要です。CUDA2/3 の指定に飛び番がある構成は resource parameter validation で拒否されます (`src/program/generate.cpp:3352-3359`)。

複数の remote GPU を使う場合、CUDA0 cache にすでに載っている pair と重複 pair を除き、profile の順位順で割り当てます。複数 remote cache を使うと、profile にない pair も補充用の候補列に追加されます。

- `stripe`: CUDA1〜3 の remote cache を順に見て空き容量のある GPU に pair を割り当て、次の検索開始位置を直前の割当先の次に進めます。各 device の slot 上限に達したものは飛ばします。
- `layer`: `pair.layer % remote GPU 数` で担当 GPU を選びます。該当 GPU の slot 上限に達した場合、その pair はそこで割り当てず、後続候補を調べます。別の GPU に空きがあっても、その layer の pair を別 GPU に付け替えません。

remote GPU 数は有効な CUDA1〜3 remote cache の数です。配置した pair は `RemoteExperts::open` に渡され、成功時には各 GPU の追加 expert 数と GiB、および pinned host rows 経由で結果が戻る旨を stderr に出します。open が失敗した場合はエラーを stderr に出して終了コード `1` になります。

CUDA1 のみの場合、`by_device[0]` に profile 順の候補列全体が渡されるため、`stripe` と `layer` の差は割り当てに現れません。なお、placement 値の不正チェック自体は remote cache の有無にかかわらず実行されます。

## 適用条件と相互作用

- `--expert-cache-device1`, `--expert-cache-device2`, `--expert-cache-device3` が remote cache の容量を指定します。CUDA1 は基準となる remote cache で、CUDA2/3 を使うには CUDA1 も指定する必要があります。
- `--expert-profile`、正の `--expert-cache`、expert pool は remote cache 初期化の前提です。`--peer-device` は remote expert cache と併用できず、併用時は終了コード `2` で拒否されます。
- `--remote-expert-opt` は placement とは別の decode 最適化で、指定する場合は `--serve` が必要です。
- 同じ parser / 配分処理が `sycl/src/program/generate.cpp` にもあります。ここでは実行バイナリや特定 backend の build を行っていないため、個別 GPU/backend 上の実動作や容量確保の結果は確認していません。

## 出力とエラー

複数 GPU の分配時には `strata generate: remote ranks striped across N CUDA devices` または `... grouped by layer across N CUDA devices` を stderr に出します。CUDA1 だけの場合はこの分配メッセージを出す分岐に入りません。値の validation エラーは終了コード `2`、remote cache open の失敗は終了コード `1` です。

## 根拠

- `src/program/generate.cpp:562` — 既定値 `stripe`。
- `src/program/generate.cpp:1003-1008` — help の値、説明、既定値。
- `src/program/generate.cpp:2418-2421,2562-2570` — 値引数の取得と parser への格納。引数走査で同じ変数を上書きする。
- `src/program/generate.cpp:3352-3363` — remote cache 容量の並びの検証、許容値と不正値のエラーコード。
- `src/program/generate.cpp:3369-3375` — `--peer-device` との併用拒否。
- `src/program/generate.cpp:6662-6671` — remote cache の有効条件と不足条件のエラー。
- `src/program/generate.cpp:6672-6693` — profile 順の候補と複数 remote cache 時の補充候補。
- `src/program/generate.cpp:6694-6729` — `stripe` / `layer` の割り当て、容量上限、CUDA1 のみの場合の分岐。
- `src/program/generate.cpp:6736-6747` — remote cache open、失敗時の終了、成功時の stderr 出力。
- `sycl/src/program/generate.cpp:540,908-909,1883-1890,2520-2529,5172-5240` — SYCL 側の同等の既定値、parser、validation、割り当て処理。
