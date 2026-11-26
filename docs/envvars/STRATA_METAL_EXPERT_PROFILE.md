# `STRATA_METAL_EXPERT_PROFILE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal の expert streaming が作る arena で、先に常駐させる expert の順位ファイルを指定する。`Window::stream_arena` はこの値をファイルパスとして `ExpertStream::make_arena` に渡す。profile に載った expert が先に arena に入り、profile にない expert は後から layer-interleaved 順で補われる。ルーターが各 token に選ぶ expert を変更する設定ではない（`engine/metal/src/engine/window.cpp:1775-1800`、`engine/metal/src/engine/stream.cpp:379-415,533-547`）。

この読み取りは Metal の `Window` にある。CUDA/HIP/SYCL や Metal の非 streaming 経路には適用されない（`engine/metal/src/engine/window.cpp:738-744`、`engine/metal/src/engine/stream.cpp:34-49`）。

## 値と判定

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| Metal の streaming arena 構築時 | `resource(nullptr, "data", STRATA_METAL_DATA_DEFAULT) + "/expert-profile.bin"` を使う | 文字列をそのままファイルパスにする。例: `/path/to/profile.bin` | 文字列形式として無効値の判定はない。空文字は「設定あり」として空パスを開こうとする。`true`、`0`、`0anything` も通常のパス文字列であり、真偽値・数値としては解釈しない（`engine/metal/src/engine/window.cpp:1775-1777`）。 |

環境変数の文字列を parse・trim・検証せず、`getenv` が null かどうかだけで既定パスとの分岐を行う。従って unset と空文字は異なる。指定パスが開けない場合は警告を出すが、arena の作成自体は続き、layer-interleaved 順を使う（`engine/metal/src/engine/stream.cpp:382-403`）。

開けたファイルは `STRP` magic と、header の layer/expert 数が現在のモデル形状と合う場合にだけ順位を読む。順位の重複・範囲外 pair は除かれ、途中で順位データを読み切れなければ、読めた順位の後を layer-interleaved で補う。ファイルを開けても header が合わない場合は順位を使わず、専用の不正形式警告は出さない（`engine/metal/src/engine/stream.cpp:379-403`）。

CLI 引数や別の環境変数との優先順位はこの読み取り箇所にはない。`STRATA_METAL_EXPERT_PROFILE` が設定されていれば、その値が既定 resource path に代わって渡される（`engine/metal/src/engine/window.cpp:1775-1777`）。

## 有効になる条件

- Metal backend の対応する `Window` が初期化されること。`Window::init` はモデル形状がコンパイル済み Qwen3.8-Flash-Next の形状に合わない場合、先に失敗する（`engine/metal/src/engine/window.cpp:714-728`）。
- expert streaming が選ばれること。`STRATA_METAL_STREAM=1` は streaming を強制し、`=0` は止める。それ以外または unset では、重みと約 12 GiB の余裕が resident footprint cap に収まらない場合に streaming を選ぶ（`engine/metal/src/engine/stream.cpp:34-49`）。
- arena の順位読み込みに使えるファイルであること。指定ファイルが開けない、または順位 header が合わない場合も streaming は継続し、layer-interleaved の順序に fallback する（`engine/metal/src/engine/stream.cpp:382-403`）。

## 実行時の詳細

環境値は `Window::stream_arena` が arena を作る段階で毎回 `getenv` から読み、static cache には保存しない。作られたパスを `make_arena` が `fopen(..., "rb")` する。arena が ready になる前の window/prompt 経路からこの関数が呼ばれ、ready 後は同じ arena を使うため、通常の実行では起動時の初回 arena 作成時に効く（`engine/metal/src/engine/window.cpp:1560,1726,1775-1802,3037-3040,3137-3140`）。

順位ファイルから有効な pair を読むと、その順に予算内の expert を fill 対象にし、読み込み後は順位順が LRU 順になる。profile の順位にない pair も全て候補に追加される。ファイルが開けない場合の stderr は `strata metal stream: no expert profile at %s: the arena starts layer-interleaved`。profile から読み込んだ順位件数は arena の完了ログ `strata metal stream: expert arena ... experts read from the profile's top (%zu ranked) ...` に現れる（`engine/metal/src/engine/stream.cpp:379-415,533-547`）。

空パスや存在しないパスは profile 不在と同じく順位なしで続行する。profile 自体の不在・形式不一致は単独では終了理由にならない。一方、arena の buffer 数が4を超える、map に失敗するなど arena 作成上の別エラーは `make_arena` が `false` を返し、呼び出し元へ伝播する（`engine/metal/src/engine/stream.cpp:450-464`、`engine/metal/src/engine/window.cpp:1560,1802`）。

## ログと測定値

Strata はファイルを開けなかった場合に上記の stderr 警告を出す。ファイルが開けても header が合わず順位を使えなかった場合、専用警告はない。正常に arena が完成すると、profile 由来の順位件数を含む stderr の arena 完了行が出る（`engine/metal/src/engine/stream.cpp:382-403,544-547`）。この変数固有の測定値は確認できない。

## 根拠

- `engine/metal/src/engine/window.cpp:714-744` — Metal `Window` の初期化と streaming 選択。
- `engine/metal/src/engine/window.cpp:1560,1726-1819` — streaming arena の作成、環境変数読み取り、既定 profile path、呼び出しと再試行。
- `engine/metal/src/engine/stream.cpp:34-49` — streaming の選択条件。
- `engine/metal/src/engine/stream.cpp:374-415,533-547` — profile の読み込み、fallback 順位、arena への反映とログ。
