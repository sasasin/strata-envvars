# `STRATA_METAL_CONTIG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Metal engine の SSD streaming 中に、GGUF の隣にある `<GGUF path>.experts` という連続配置コピーを使うかを選びます。既定ではそのファイルを開いて形式・サイズ・内容を確認し、適合すれば expert をそこから読みます。`0` を指定すると sidecar を試さず、元の GGUF から読みます。これは streaming 自体の有効・無効を切り替える変数ではありません。

環境変数を読む箇所は `metal/src/engine/stream.cpp:27-30,76` の一つです。`env_int` は名前を引数で受けますが、全呼び出し箇所を確認した結果、この名前を渡す呼び出しは `ExpertStream::open()` 内の同箇所だけでした。直接参照の他の二箇所は `metal/src/engine/stream.h:95-97` と `docs/MAC.md:258` の説明です。

## 値と判定

helper は未設定または空文字なら既定値を返し、それ以外は `std::atoi` の戻り値を返します。呼び出し側は結果が `0` かどうかだけで分岐します。文字列全体の検証、エラー検出、範囲制限はありません。

| 環境値 | 判定 | 結果 |
|---|---|---|
| 未設定 | helper の既定値 `1` | `.experts` を試す |
| 空文字 | `*e` が偽なので既定値 `1` | `.experts` を試す |
| `0` に変換される非空文字列（例: `0`, `false`, `abc`） | `atoi` の結果が `0` | `.experts` を試さず GGUF から読む |
| `0` 以外の整数値に変換される文字列（例: `1`, `-1`, `2tail`） | `atoi` の結果が非ゼロ | `.experts` を試す |

`atoi` のため、数値の前の空白や符号は変換対象になり、数値として読める接頭辞の後ろは検査されません。整数範囲外の入力について、このコードに独自のエラー処理や境界規則はありません。

## 有効になる条件

- Metal 用のビルドであることが前提です。`metal/CMakeLists.txt:57-62` は Metal runtime に `STRATA_GPU_METAL=1` を定義し、`src/core/verify.cpp:801-804` はその macro の経路で Metal window を初期化します。CUDA/HIP の通常経路ではこの Metal engine の読み取り箇所に到達しません。
- Metal window は `metal/src/engine/window.cpp:530-533` で Qwen3.8-Flash-Next と一致する geometry を要求します。モデルファイルを開いた後、`ExpertStream::wanted()` が streaming を選んだ場合だけ `ExpertStream::open()` が呼ばれ、そこで本変数が評価されます（`metal/src/engine/window.cpp:541-548`）。
- streaming の選択は別変数 `STRATA_METAL_STREAM` が文字列全体で `1` なら強制 ON、`0` なら強制 OFF、それ以外または未設定なら resident footprint 判定です。自動判定では、モデル tensor bytes と 12 GiB の余裕が resident cap に収まらない場合に streaming になります（`metal/src/engine/stream.cpp:33-47`, `metal/src/engine/arena_budget.h:135-142`）。`STRATA_METAL_STREAM=0` または自動判定で常駐経路になった場合、本変数は読まれません。
- CLI 引数や別設定による `STRATA_METAL_CONTIG` 自体の上書きは見つかりません。`STRATA_METAL_STREAM` は streaming 経路を決める先行条件であり、本変数の値を置き換えません。

## 実行時の詳細

`ExpertStream::open()` は GGUF を開き、48 layer 分の routed expert tensor の存在を確認してから本変数を一度読みます（`metal/src/engine/stream.cpp:60-76`）。判定結果は sidecar file descriptor `cfd_` に反映され、その `ExpertStream` が使われている間、後続の expert 読み込みは環境を再評価せず `cfd_` に従います。プロセス起動後に環境を変更しても、既に開いた stream の読み先は切り替わりません。新しい `open()` 呼び出しでは再評価されます。

非ゼロなら `<GGUF path>.experts` を読み取り専用で開きます。開けた場合は `STRX` magic、version 1、48 layers、512 experts、GGUF のファイルサイズ、各 layer の gate/up/down slice サイズを照合し、さらに layer 0 の先頭 expert と layer 47 の末尾 expert の全 slice を GGUF と比較します（`metal/src/engine/stream.cpp:77-107`）。検証に通れば sidecar を使い、stderr に `strata metal stream: experts read from <path> (one request per expert)` と出します（同 `:110-115`）。sidecar が存在しないときは `open()` が失敗して `cfd_` は `-1` のままですが、ここでは警告を出さず GGUF 読みに進みます。sidecar が開けても検証に失敗した場合は閉じ、stderr に `strata metal stream: <path> is not this GGUF's (sizes or bytes differ): the GGUF is read` と出します（同 `:116-120`）。

`STRATA_METAL_CONTIG=0` 相当の判定では sidecar の open/検証を行いません。`cfd_` の初期値は `-1` であり、`read_part()` は元 GGUF の gate/up/down slice を個別に読みます。sidecar が有効な場合は expert 全体の連続配置から読みます（`metal/src/engine/stream.h:95-98`, `metal/src/engine/stream.cpp:275-305`）。読み込み自体が失敗すると stderr に `strata metal stream: reading expert <e> of layer <l> failed` を出して `exit(6)` します（同 `:283-303`）。

`docs/MAC.md:258` の「`STRATA_METAL_CONTIG=0` は experts copy があっても model file を読む」という記述は、ソースの分岐と一致します。

## 根拠

- 候補名の全参照: `metal/src/engine/stream.cpp:76`, `metal/src/engine/stream.h:96`, `docs/MAC.md:258`。候補一覧 `docs/envvars/000_envvers.md:1029` に名前があります。
- 値の既定・変換: `metal/src/engine/stream.cpp:27-30,76`。
- streaming と Metal window の条件: `metal/src/engine/stream.cpp:33-47`, `metal/src/engine/window.cpp:530-548`, `metal/CMakeLists.txt:57-62`, `src/core/verify.cpp:801-804`。
- sidecar の検証、fallback、ログ: `metal/src/engine/stream.cpp:74-120`。
- 読み先と読み込み失敗: `metal/src/engine/stream.h:95-98`, `metal/src/engine/stream.cpp:275-305`。
