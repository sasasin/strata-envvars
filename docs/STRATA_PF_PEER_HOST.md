# `STRATA_PF_PEER_HOST`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

peer GPU と primary GPU の間に P2P アクセスがないとき、prefill の peer 計算を mapped pinned host memory 経由で行う経路を許可するか決めます。既定では許可されます。無効にすると peer prefill の初期化を断り、prompt path は primary GPU のみで続行します。この変数は decode 用 peer tier 自体の有効・無効を切り替えるものではありません。

## 値と判定

`src/prefill/prefill.cpp` は `std::getenv()` の結果を `std::atoi()` に渡し、値が未設定なら許可、設定されていれば変換結果が 0 以外のとき許可とします。文字列全体の厳密な数値検証はありません。

| 設定値 | 判定 |
|---|---|
| 未設定 | 許可 |
| `0`、空文字、数字に変換できない文字列（例 `off`） | 不許可（`atoi` が 0） |
| 整数として 0 以外になる文字列（例 `1`, `-1`, `2`） | 許可 |
| 数字の後ろに文字が続く文字列（例 `1xyz`, `0xyz`） | 数字の先頭部分で変換され、それぞれ許可、不許可 |

`atoi` のため先頭空白や符号も変換規則に従います。範囲 clamp、警告ログ、明示値と CLI・設定ファイルの優先順位はありません。

## 有効になる条件

- `--peer-device` で有効な peer tier があり、`--peer-prefill-rows` が 0 でない場合に、serve 起動時の prompt path 初期化から `set_peer()` が呼ばれます。`--peer-prefill-rows` の既定値は -1 で、chunk × top-k の半分の行数を使います。
- この環境変数が拒否判定に使われるのは `peer->p2p()` が false の場合だけです。P2P が使える場合は、この値にかかわらず peer prefill の初期化を続けます。
- P2P の有無は両 GPU 間の peer access 能力と有効化結果で決まり、`STRATA_PEER_NO_P2P` が非ゼロなら実装上 P2P なしとして扱います。この関連変数は P2P 経路の判定を変え、それを介して本変数の適用場面にも影響します。
- 拒否判定に当たらなくても、MMQ prompt path がない場合や peer 用リソース確保に失敗する場合など、別の理由で peer prefill が初期化されないことがあります。

## 実行時の詳細

`set_peer()` は peer が無効なら何も設定せず成功扱いで戻ります。有効な peer について、P2P がなく、かつ本変数が不許可なら `prefill peer: the two GPUs cannot access each other (no P2P)` をエラー文字列に設定して失敗を返します。許可時は peer の状態を `p2p=false` として保持し、activations や peer の計算結果などに使う mapped pinned host buffers を確保します。後続処理はこの host route を使います。

serve 側の呼び出し元は `set_peer()` が失敗した場合、stderr に `strata serve: <エラー> - the prompt path stays on the primary GPU` を出し、エラーを消去して起動を続けます。したがって本変数を 0 にしても、peer tier の他の用途まで停止するわけではなく、peer を使う prefill 初期化だけが諦められます。

環境変数は `set_peer()` の呼び出しごとに読み取られ、`static` cache されません。通常の serve 経路では prompt path 初期化中に判定されるため、その後の環境変更で既に作成された peer prefill の状態は変わりません。

## 根拠

- `src/prefill/prefill.cpp:1649-1656` — `getenv` / `atoi` 判定、P2P なし時の拒否とエラー。
- `src/prefill/prefill.cpp:626-643,1767-1798` — P2P なしの mapped host route と pinned buffer の確保。
- `src/prefill/prefill.cpp:1803-1812` — peer prefill の初期化ログと route 表示。
- `src/core/peer_experts.cpp:97-111` — P2P 能力判定、有効化、`STRATA_PEER_NO_P2P` の影響。
- `src/program/generate.cpp:479-481,7368-7373` — `--peer-prefill-rows` の既定と、初期化失敗時に primary GPU の prompt path へ続行する処理。
- `src/program/generate.cpp:868-875` — `--peer-device` と `--peer-prefill-rows` の CLI 説明。
- `docs/DETAILS.md:773-785` など関連説明を確認しましたが、`STRATA_PF_PEER_HOST` 固有の値判定・挙動の説明は見当たりませんでした。
