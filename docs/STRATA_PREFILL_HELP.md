# `STRATA_PREFILL_HELP`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

レイヤー分割した複数 GPU のプロンプト処理で、現在のステージが MoE 専門家を読み込んでいる間にアイドル状態になる次のステージの GPU を使い、ストリーム対象の専門家の一部を計算させる機能を有効にする。環境変数を有効にしても、後述の条件を満たすプロンプトだけで動く。未設定時は無効。

## 値と判定

| 環境変数の値 | 判定 |
| --- | --- |
| 未設定 | 無効 |
| 空文字、数字で始まらない文字列、`0`、`0abc` | 無効 |
| `1`、その他 `atoi` が 0 以外に変換する値（例: `-1`, `2`, `1abc`） | 有効 |

実装は `std::getenv` の結果を `std::atoi` に渡し、変換結果が 0 以外なら有効とする。したがって真偽値文字列の `true` は有効にならず、先頭の空白・符号と数字列は変換され、数字列より後ろは判定に使われない。設定値の数値範囲チェックはない。

値は `Prefill::set_stage_helper` から最初に呼び出された際に関数内の `static` 値として読み取られる。以後同じプロセス内で環境を変更しても反映されないため、設定変更にはプロセスの再起動が必要。CLI 引数でこの環境変数を上書きする処理は見つからなかった。

## 有効になる条件

- `strata serve` のレイヤー分割（複数 GPU ステージ）経路で各ステージの `Prefill` に次のステージの `Prefill` を helper として設定する。通常の単一 GPU 経路や `--peer-device` のみの経路では、この helper を設定する呼び出しに入らない。
- ステージと helper が別の有効 GPU を持ち、対象ステージの MMQ 計画に対象レイヤーが含まれている必要がある。
- 実際のプロンプト処理では一つのチャンクで読み切る場合に限る。デフォルトでは 1024 トークン以上のチャンク、デフォルトの共有率計算が正の値になる概ね 3276 トークン以下のチャンクが対象となる。チャンク上限や共有率は `STRATA_PREFILL_STREAM_MIN` と `STRATA_PREFILL_HELP_FRAC` によって変わる。
- 入力元とステージのリング、helper 側の MMQ バッファが利用でき、 fused ring 経路でなく、対象レイヤーが helper 側で計算可能である必要がある。これらを満たさない場合はそのプロンプトで helper を使わず通常の処理を続ける。
- native expert pack では対象レイヤーに fused カーネルが使える場合、この helper 経路を使わない。`docs/MULTI_GPU.md` は fused prompt kernels (`STRATA_PF_FUSED=1`) と `--peer-device` を対象外として説明している。

デフォルトの共有率は `min(0.45, 0.5 - T / 16384)`（`T` はチャンクのトークン数）で、0.3 未満なら 0 にする。共有率が 0 の場合も helper 計算は行われない。なお、`STRATA_PREFILL_HELP_FRAC` が設定されるとその値を `atof` で読み、0〜1 に clamp した固定共有率を使う。

## 実行時の詳細

サーバー起動時に各ステージへ次ステージの GPU を helper として関連付ける。有効な場合、実装は helper の GPU にストリームとイベントを作る。作成に失敗した場合、`strata serve: <エラー> - stage <番号> reads its prompts alone` を stderr に出し、そのステージは単独で読む。

一チャンクのプロンプト処理開始時に helper のバッファを結び付ける。共有対象に選ばれた専門家の重みは helper GPU の PCIe 経由でその GPU 自身のプロンプト用バッファへ転送され、helper が MMQ 経路で行を計算して結果を返す。コードでは転送対象を `ps_frac` の累積で選び、活性値と結果行には mapped host memory を通す経路を使う。処理終了時に helper のストリームを同期し、ステージ間の役割を戻す。

環境変数が有効でも、条件に合わない場合の多くは追加ログなしで通常処理に戻る。helper 経路の計測が有効な場合、peer GPU のタイミングと `peer-streamed experts` 数が stderr に出る。helper が計算する行は別の MMQ grouping で丸められるため、既定経路と bit-identical ではない。Strata の資料は同じプロンプトに対しては再現可能と記し、この理由で opt-in としている。

## 根拠

- `src/prefill/prefill.cpp:1513-1518` — 変数を `getenv` / `atoi` で読み、非ゼロ判定を static cache。
- `src/prefill/prefill.cpp:1538-1575` — helper 設定条件、GPU ストリームとイベントの作成。
- `src/prefill/prefill.cpp:1580-1640` — 一チャンク時の適用条件、MMQ 条件、helper バッファ割当。
- `src/prefill/prefill.cpp:2077-2094` — 一チャンク時の bind と helper 処理後の同期・復元。
- `src/prefill/prefill.cpp:2325-2355` — `ps_frac` に基づく専門家の振り分け。
- `src/prefill/prefill.cpp:148-152` — デフォルトのストリーミング開始トークン数（1024）。
- `sycl/src/prefill/prefill.cpp:1506-1534` — SYCL 実装にも同じ環境変数の判定と helper 設定がある。
- `src/program/generate.cpp:7305-7315` — サーバーのレイヤー分割ステージに helper を設定し、設定失敗時に stderr へ通知。
- `docs/MULTI_GPU.md:85-101` — 機能の説明、適用上限、非 bit-identical の記載、および 2x RTX 3090 / UD-Q4_K_XL / no P2P の測定例。記載された prompt tok/s は 1.1K で 496→723、1.5K で 674→833、2K で 878→1,128、2.5K で 1,017→1,296、3K で 1,260→1,440。これは資料の測定値であり、本調査で再測定した値ではない。
