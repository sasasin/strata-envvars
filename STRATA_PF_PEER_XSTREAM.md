# `STRATA_PF_PEER_XSTREAM`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CUDA の `--peer-device` を使う prompt 処理で、2枚の GPU 間に P2P 経路がなく、mapped host memory を経由する場合に、primary GPU と host 間のコピーを専用 CUDA stream に置くか、primary の計算 stream に置くかを選びます。既定では専用 stream を作ります。値を変えても peer の行の割り当てや演算を直接変える処理はありません。

## 値と判定

`Prefill::set_peer()` で `std::getenv()` と `std::atoi()` を使い、一度の prompt path 初期化時に判定します。文字列全体の妥当性検査はなく、`atoi` が変換した整数が 0 かどうかで分岐します。

| 状況 | 判定・動作 |
|---|---|
| unset | unset 用の条件分岐で専用 stream と event の作成を試みる |
| `0`、空文字、数値に変換できない文字列（例: `abc`） | `atoi` が 0 を返し、専用 stream を作らない。コピーは primary の計算 stream を使う |
| `1`、その他 `atoi` が非 0 を返す値（例: `2`, `-1`, `2tail`） | 専用 stream と event の作成を試みる |

空白や符号、数値の後ろの文字は `atoi` の変換規則に従います。たとえば `0tail` は 0、`1tail` は 1 になります。設定値を初期化後に変更しても、この `PeerPrefill` の選択は再評価されません。

根拠: `src/prefill/prefill.cpp:1649-1673`。

## 有効になる条件

- CUDA の `--peer-device` prompt 経路で `Prefill::set_peer()` が成功すること。server は peer が有効で `--peer-prefill-rows` が 0 でない場合に設定を呼びます。既定の行数は prompt chunk の半分です（`src/program/generate.cpp:7368-7372`）。
- peer GPU との P2P が使えないこと（`peer->p2p()` が false）。P2P 経路ではこの環境変数を読みません。P2P が使えない場合でも `STRATA_PF_PEER_HOST=0` なら peer prompt 経路自体が拒否されます（`src/prefill/prefill.cpp:1652-1655`）。
- peer prompt の MMQ 経路が利用可能であること。`mmq_plan().any` が false なら初期化を拒否します（`src/prefill/prefill.cpp:1656`）。

したがって、変数を設定しても P2P 経路、peer prompt を無効にした設定、または peer prompt の初期化に失敗した場合には stream 選択へ影響しません。専用 stream/event の作成に失敗すると `set_peer()` は `prefill peer: copy stream` を返し、呼び出し元は「the prompt path stays on the primary GPU」と stderr に出して peer prompt を設定しません。

## 実行時の詳細

P2P のない経路で値が unset または非 0 の場合、`set_peer()` は primary 側の `x_stream` と `ev_x` を作成します。各 layer で peer 向け処理を始める際、primary の計算 stream `m.cs` に event を記録し、専用 stream がその event を待ってから activation や routing data の host 向け転送を行います。転送の完了 event `ev_in` も同じ選択 stream に記録され、peer 側の stream はそれを待って計算を始めます。この配置により、host 経由コピーを primary の expert 計算と並行して進められる構成です。

値が `atoi` で 0 になる場合は `x_stream` が null のままなので、同じ転送処理は `m.cs` 上に enqueue されます。専用 stream を選んだ場合、`PeerPrefill` の破棄時に stream を同期してから破棄します。専用 stream はコピーの stream 配置だけを変え、peer の演算結果を primary に戻して prompt 結果へ加える処理は共通です。

根拠: `src/prefill/prefill.cpp:645-646,664-686,1665-1673,3398-3427`。

## 文書との照合

`docs/SECOND_GPU.md:131-148` は `--peer-device` による peer prompt と `--peer-prefill-rows` を説明していますが、`STRATA_PF_PEER_XSTREAM` の記載はありませんでした。値ごとの挙動は上記の実装に基づきます。

## 根拠

- `src/prefill/prefill.cpp:1649-1673` — peer prompt 初期化、P2P 判定、環境変数の読み取りと stream/event 作成。
- `src/prefill/prefill.cpp:3398-3427` — primary 計算 stream と host route copy stream の event 依存関係、および activation/weight 転送。
- `src/prefill/prefill.cpp:645-646,664-686` — stream/event の保持と破棄。
- `src/program/generate.cpp:7368-7372` — server 側の peer prompt 初期化呼び出しと失敗時のログ。
