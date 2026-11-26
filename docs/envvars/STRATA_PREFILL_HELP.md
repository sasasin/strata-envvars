# `STRATA_PREFILL_HELP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。調査時の checkout は `## main...origin/main` で、未コミット変更はありませんでした。

## 役割

多 GPU の layer split で、prompt の各 stage が通常は自分で処理する streamed expert の一部を、次の stage（最後の stage の次は最初の GPU）の idle GPU に MMQ で計算させる opt-in です。単なる設定確認ではなく、streamed expert の割当て、別 GPU への入力・結果の受け渡し、MoE 行の結合を変えます。helper の MMQ grouping が通常経路と異なるため、ソースは結果が bit-identical ではないとしています（`engine/src/prefill/prefill.cpp:3173-3178`、`engine/src/program/generate.cpp:13155-13167`、`engine/src/prefill/prefill.cpp:4703-4717`、`engine/src/prefill/prefill.cpp:7617-7630`）。

同じ名前は CUDA/HIP 系の `engine/src/prefill/prefill.cpp:3176-3178` と SYCL 系の `engine/sycl/src/prefill/prefill.cpp:2063-2065` で読み取られます。さらに、pipelined concurrent read の適用可否を決める `engine/src/program/generate.cpp:21024-21033` でも env helper を通じて読み取られます。この二つ目は helper の実行を有効化する読み取りではなく、同時読み込みを止める理由判定です。

## 値と判定

両 Prefill 実装とも `std::getenv` の結果を `std::atoi` に渡し、結果が 0 以外なら有効とします。文字列全体の検証や `true` / `false` の解釈はありません（`engine/src/prefill/prefill.cpp:3176-3178`、`engine/sycl/src/prefill/prefill.cpp:2063-2065`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| CUDA/HIP 系または SYCL 系 Prefill の helper 設定 | `false` | `1`、`2`、`-1`、`+1`、`1tail`（先頭の整数変換結果が非 0） | 空文字、`0`、`0tail`、`true`、`false`、整数として読める先頭部分がない文字列 |
| `STRATA_PIPED_CONCURRENT` の可否判定内の helper | この箇所では未設定なら `false` | `1`、`-1`、`1tail` | 空文字、`0`、`0tail`、`true`、整数として読める先頭部分がない文字列 |

`atoi` は先頭の空白と符号を含む整数部分を読み、後続文字を検証しません。したがって `1.0` や `1anything` は有効、`0anything` は無効です。`true` / `false` は数値変換できず 0 になります。数値範囲外の文字列に対する `atoi` の結果は C/C++ の規則上保証されず、Strata に独自の範囲検査はありません。未設定・空文字・変換結果 0 では helper は無効です。CLI 引数からこの値を上書きする処理は確認できません。

## 有効になる条件

値が非 0 でも、実際に helper が使われるには以下を満たす必要があります。

- Engine が複数 GPU の layer split で動き、prompt path と split stages が初期化されていること。生成側は `multi_gpu && !stages.empty()` の場合に各 stage と次の stage を `set_stage_helper` で結びます（`engine/src/program/generate.cpp:13155-13167`）。通常の単一 GPU 経路ではこの設定呼び出しがありません。
- helper 設定時に両 GPU の device id が有効かつ異なり、MMQ plan に対応層があること。CUDA 系では `STRATA_PF_OWN_ONLY` build の場合、これらの判定後に helper を設定せず戻ります（`engine/src/prefill/prefill.cpp:3212-3221`）。
- prompt が一回の run で一 chunk と判定されること。chunked read では `single_chunk` が false になり helper を bind しません（`engine/src/prefill/prefill.cpp:4295-4304`）。`--prefill` や `--prefill-pipe` 等で分割された場合も、この条件に従います。
- chunk の token 数 `T` が `stream_all_min()` 以上で、expert source があり、stage の ring が通常 stage より大きく、fused ring でないこと（`engine/src/prefill/prefill.cpp:3258-3266`）。このときだけ全 streamed expert を対象にした stream 計画に進みます。
- 対象 stage の全層が MMQ 対応であり、native pack の場合はその層の native fused kernel が未対応であること（`engine/src/prefill/prefill.cpp:3263-3266`）。SYCL 側にも同じ条件があります（`engine/sycl/src/prefill/prefill.cpp:2158-2166`）。
- helper stage 側に対象 chunk 分の必要な prompt buffers と MMQ context があること（`engine/src/prefill/prefill.cpp:3268-3273`）。条件を満たさない場合はその prompt で helper を使わず通常経路に戻ります。
- `STRATA_PREFILL_HELP_FRAC` が 0 相当でないこと。これは別変数ですが、未設定時は `T` に応じた割合を使い、設定時は `atof` の値を `[0,1]` に clamp します。割合が 0 以下なら bind を拒みます（`engine/src/prefill/prefill.cpp:3180-3194`、`engine/src/prefill/prefill.cpp:3261-3266`）。

`STRATA_PIPED_CONCURRENT` が非 0 の場合は別の相互作用があります。`env_on("STRATA_PREFILL_HELP")` も `atoi != 0` で値を見て、layer split helper が実際に使えるかどうかにかかわらず、concurrent read を止める理由を `STRATA_PREFILL_HELP` として返します（`engine/src/program/generate.cpp:21024-21046`、`engine/include/strata/program/batch_read.hpp:43-53`）。

## 実行時の詳細

CUDA/HIP 系と SYCL 系それぞれの `split_help_env()` は関数内 `static` に判定結果を保存します。値はその実装で最初に `set_stage_helper` が判定された時に読み取られ、そのプロセス内では以後の環境変更は反映されません（`engine/src/prefill/prefill.cpp:3176-3178,3212-3217`、`engine/sycl/src/prefill/prefill.cpp:2063-2065,2085-2090`）。`STRATA_PIPED_CONCURRENT` の可否判定にも独立した関数内 `static` があり、同時読み込み判定が初めて評価された時に env helper が読みます（`engine/src/program/generate.cpp:21024-21046`）。

helper の stream/event 群は layer split の prompt path 初期化時に作られます。対象 chunk の bind では helper stage の MMQ 用 buffers を結び、`STRATA_PREFILL_HELP_FRAC` による割合を設定します（`engine/src/prefill/prefill.cpp:3212-3253,3258-3318`）。prompt run は `single_chunk` かつ bind 成功時に peer/helper を有効にし、run 終了時に helper stream を同期して元の状態へ戻します（`engine/src/prefill/prefill.cpp:4303-4316`）。

stream-all 対象の MoE 層では、expert source の pinned expert を割合に応じて helper 用 ring に送り、残りは prompt 側の stream sequence に残します。helper が計算した行は peer 側の行ブロックとして扱われ、完了待ちの後に prompt 側の MoE 結合へ戻します（`engine/src/prefill/prefill.cpp:4641-4717,6059-6079,7617-7630`）。したがって変わるのは prompt の expert 計算分担とその浮動小数点計算経路で、decode の設定を直接変える処理ではありません。

helper 初期化時の stream/event 作成失敗は `set_stage_helper` がエラーを返し、生成側は stderr に `strata serve: <error> - stage <n> reads its prompts alone` と出して、その stage を単独で読む経路にします（`engine/src/prefill/prefill.cpp:3245-3253`、`engine/src/program/generate.cpp:13160-13166`）。prompt ごとの bind 条件不足や pinned host buffer の確保失敗は `false` を返すだけで、この箇所には理由ログがありません（`engine/src/prefill/prefill.cpp:3260-3273,3297-3314`）。SYCL の `set_stage_helper` で例外が捕捉された場合は例外文と source location を stderr に出して `exit(1)` します（`engine/sycl/src/prefill/prefill.cpp:2150-2153`）。

## ログと測定値

`STRATA_PIPED_CONCURRENT` が有効な状態で concurrent read が評価され、他の理由より先にこの変数が該当すると、stderr に次の形式で出ます（変数自身を有効化した際の helper 成功ログではありません）。

```text
strata batch: STRATA_PIPED_CONCURRENT is off beside STRATA_PREFILL_HELP
```

理由の優先順位は `concurrent_read_off` の判定順に依存します（`engine/src/program/generate.cpp:21041-21043`、`engine/include/strata/program/batch_read.hpp:43-53`）。helper 自体の成功時に常時出る専用ログは見つかりません。`STRATA_PREFILL_TIMING` が設定されて timing 出力が有効な場合は peer GPU の時間と、`ps_frac > 0` なら `strata prefill timing: peer-streamed experts ...` の行数を stderr に出します（`engine/src/prefill/prefill.cpp:4057-4059,7992-8005`）。

ソースコメントには 2x RTX 3090、UD-Q4_K_XL、各 PCIe 4.0 x16、P2P なしの測定として、固定 share 0.2 / 0.3 / 0.4 と share なしを比べた prompt tok/s が記録されています。1.5K tokens では 749 / 820 / 908（なし 675）、3K では 1335 / 1437 / 1328（なし 1262）、4K では 1622 / 1620 / 1440（なし 1609）、6K では 1811 / 1660 / 1471（なし 2038）、8K では 1895 / 1804 / 1663（なし 2230）です。測定回数などはコメントにないため一般化できません（`engine/src/prefill/prefill.cpp:3180-3186`）。同じ条件と注記は SYCL 実装にも記載されています（`engine/sycl/src/prefill/prefill.cpp:2067-2073`）。

## 根拠

- `engine/src/prefill/prefill.cpp:3173-3195` — 値の取得・cache、share の既定計算。
- `engine/src/prefill/prefill.cpp:3212-3253,3258-3318` — CUDA/HIP 系の helper 初期化と prompt bind 条件。
- `engine/src/prefill/prefill.cpp:4295-4316,4641-4717,6059-6079,7617-7630` — 一 chunk 判定、streamed expert の割当て、結果行の結合。
- `engine/sycl/src/prefill/prefill.cpp:2060-2082,2085-2166` — SYCL 系の対応実装。
- `engine/src/program/generate.cpp:13155-13167,21024-21046`、`engine/include/strata/program/batch_read.hpp:30-53` — helper の接続と concurrent read 側の間接参照。
- `engine/src/prefill/prefill.cpp:4057-4059,7992-8005` — timing を有効にした場合の観測ログ。
